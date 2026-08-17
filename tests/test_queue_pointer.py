# -*- coding: utf-8 -*-
"""Unit tests for VacancyRadar queue pointer / hotkey selection / letters."""
from __future__ import annotations

import json

from radar.cover_letter import make_cover_letter
from radar.queue_store import Vacancy, is_hotkey_white, pick_next_vacancy, QueueStore, norm_url


def _v(n: int, status: str = "new", **kw) -> Vacancy:
    found = kw.pop("found_at", f"2026-08-15T10:00:{n:02d}+00:00")
    return Vacancy(
        id=f"id-{n}",
        title=f"Title {n}",
        company=f"Co {n}",
        url=f"https://hh.ru/vacancy/{1000 + n}",
        score=80 + n,
        status=status,
        found_at=found,
        cover_letter=kw.pop("cover_letter", "letter"),
        reasons=kw.pop("reasons", ["+20 remote"]),
        **kw,
    )


class TestNormUrl:
    def test_strips_query_and_normalizes(self):
        assert norm_url("https://hh.ru/vacancy/123?query=1") == "https://hh.ru/vacancy/123"


class TestPickNextVacancy:
    def test_newest_white_first(self):
        # larger found_at = newer
        items = [_v(1, "new", found_at="2026-08-15T10:00:01+00:00"), _v(2, "new", found_at="2026-08-15T12:00:00+00:00")]
        got = pick_next_vacancy(items, "")
        assert got and got.url.endswith("/1002")

    def test_advances_to_older_after_active(self):
        items = [
            _v(1, "new", found_at="2026-08-15T10:00:00+00:00"),
            _v(2, "new", found_at="2026-08-15T11:00:00+00:00"),
            _v(3, "new", found_at="2026-08-15T12:00:00+00:00"),
        ]
        newest = pick_next_vacancy(items, "")
        assert newest and newest.url.endswith("/1003")
        next_older = pick_next_vacancy(items, newest.url)
        assert next_older and next_older.url.endswith("/1002")
        oldest = pick_next_vacancy(items, next_older.url)
        assert oldest and oldest.url.endswith("/1001")

    def test_wraps_to_newest(self):
        items = [
            _v(1, "new", found_at="2026-08-15T10:00:00+00:00"),
            _v(2, "new", found_at="2026-08-15T12:00:00+00:00"),
        ]
        got = pick_next_vacancy(items, items[0].url)  # active = oldest
        assert got and got.url.endswith("/1002")

    def test_skips_applied_and_hh_awaiting(self):
        items = [
            _v(1, "applied"),
            _v(2, "new", hh_status="awaiting"),
            _v(3, "new", hh_status="interview"),
            _v(4, "new"),
        ]
        got = pick_next_vacancy(items, "")
        assert got and got.url.endswith("/1004")

    def test_visited_without_apply_is_white(self):
        items = [_v(1, "visited"), _v(2, "applied")]
        assert is_hotkey_white(items[0])
        assert not is_hotkey_white(items[1])
        got = pick_next_vacancy(items, "")
        assert got and got.url.endswith("/1001")

    def test_empty(self):
        assert pick_next_vacancy([], "") is None
        assert pick_next_vacancy([_v(1, "banned")], "") is None


class TestQueueStoreOpenNext:
    def test_open_next_uses_active_and_persists(self, tmp_path, monkeypatch):
        q = tmp_path / "queue.json"
        s = tmp_path / "seen.json"
        q.write_text(json.dumps({"items": [], "pointer": 0, "active_url": ""}), encoding="utf-8")
        s.write_text("[]", encoding="utf-8")
        monkeypatch.setattr("radar.queue_store.QUEUE_PATH", q)
        monkeypatch.setattr("radar.queue_store.SEEN_PATH", s)

        store = QueueStore(autoload=True)
        store.items = [
            _v(1, "new", found_at="2026-08-15T10:00:00+00:00"),
            _v(2, "new", found_at="2026-08-15T11:00:00+00:00"),
        ]
        store.save()

        first = store.open_next()
        assert first and first.url.endswith("/1002")
        first.status = "visited"
        store.set_active(first.url)

        second = store.open_next()
        assert second and second.url.endswith("/1001")
        assert second.url != first.url

        raw = json.loads(q.read_text(encoding="utf-8"))
        assert raw["active_url"].endswith("/1002")

    def test_ban_removes_from_queue_keeps_seen(self, tmp_path, monkeypatch):
        q = tmp_path / "queue.json"
        s = tmp_path / "seen.json"
        q.write_text(json.dumps({"items": [], "pointer": 0, "active_url": ""}), encoding="utf-8")
        s.write_text("[]", encoding="utf-8")
        monkeypatch.setattr("radar.queue_store.QUEUE_PATH", q)
        monkeypatch.setattr("radar.queue_store.SEEN_PATH", s)

        store = QueueStore(autoload=True)
        a = _v(1, "new")
        b = _v(2, "new")
        store.items = [a, b]
        store.seen.add(a.url)
        store.seen.add(b.url)
        store.set_active(a.url)
        store.mark(a.url, "banned")

        assert all(v.url != a.url for v in store.items)
        assert a.url in store.seen
        assert store.active_url == ""
        assert store.known(a.url)


class TestCoverLetter:
    def test_local_letter_has_contacts_and_no_score_leak(self):
        from unittest.mock import patch

        cfg = {
            "python_only": True,
            "portfolio_url": "https://example.com/portfolio",
            "telegram": "@tester",
            "email": "tester@example.com",
            "candidate_role": "Специалист",
            "experience_years_label": "1",
            "candidate_pitch": "Тестовый питч.",
            "work_format_phrase": "Ищу удалённую работу",
            "salary_target": 100000,
        }
        with patch("radar.cover_letter.load_config", return_value=cfg):
            letter, src = make_cover_letter(
                "Vue Developer",
                company="TestCo",
                description="Need Vue 3 TypeScript remote",
                salary="160000",
                reasons=["+25 Vue 3", "+20 remote", "Score: 87%", "Why:"],
                force_local=True,
            )
        assert src == "local"
        assert "https://example.com/portfolio" in letter
        assert "@tester" in letter
        assert "tester@example.com" in letter
        assert "Vue Developer" in letter
        assert "Score:" not in letter
        assert "+25 Vue 3" not in letter


class TestHotkeyBusySemantics:
    def test_pick_sequence_newest_to_oldest(self):
        items = [
            _v(10, "new", found_at="2026-08-15T10:00:00+00:00"),
            _v(20, "new", found_at="2026-08-15T11:00:00+00:00"),
            _v(30, "new", found_at="2026-08-15T12:00:00+00:00"),
        ]
        active = ""
        opened = []
        for _ in range(3):
            v = pick_next_vacancy(items, active)
            assert v is not None
            opened.append(v.url)
            v.status = "visited"
            active = v.url
        assert opened == [items[2].url, items[1].url, items[0].url]
