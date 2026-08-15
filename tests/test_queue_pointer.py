# -*- coding: utf-8 -*-
"""Unit tests for VacancyRadar queue pointer / hotkey selection / letters."""
from __future__ import annotations

import json

from radar.cover_letter import make_cover_letter
from radar.queue_store import Vacancy, pick_next_vacancy, QueueStore, norm_url


def _v(n: int, status: str = "new", **kw) -> Vacancy:
    return Vacancy(
        id=f"id-{n}",
        title=f"Title {n}",
        company=f"Co {n}",
        url=f"https://hh.ru/vacancy/{1000 + n}",
        score=80 + n,
        status=status,
        cover_letter=kw.pop("cover_letter", "letter"),
        reasons=kw.pop("reasons", ["+20 remote"]),
        **kw,
    )


class TestNormUrl:
    def test_strips_query_and_normalizes(self):
        assert norm_url("https://hh.ru/vacancy/123?query=1") == "https://hh.ru/vacancy/123"


class TestPickNextVacancy:
    def test_first_new_when_no_active(self):
        items = [_v(1, "visited"), _v(2, "new"), _v(3, "new")]
        got = pick_next_vacancy(items, "")
        assert got and got.url.endswith("/1002")

    def test_advances_to_next_new_after_active(self):
        items = [_v(1, "new"), _v(2, "new"), _v(3, "new")]
        active = items[0].url
        got = pick_next_vacancy(items, active)
        assert got and got.url == items[1].url

    def test_wraps_single_new(self):
        items = [_v(1, "visited"), _v(2, "new"), _v(3, "visited")]
        got = pick_next_vacancy(items, items[1].url)
        assert got and got.url == items[1].url

    def test_skips_applied_banned_skipped(self):
        items = [
            _v(1, "banned"),
            _v(2, "applied"),
            _v(3, "skipped"),
            _v(4, "new"),
        ]
        got = pick_next_vacancy(items, "")
        assert got and got.url.endswith("/1004")

    def test_after_all_visited_moves_forward(self):
        items = [_v(1, "visited"), _v(2, "visited"), _v(3, "visited")]
        got = pick_next_vacancy(items, items[0].url)
        assert got and got.url == items[1].url

    def test_cycle_visited(self):
        items = [_v(1, "visited"), _v(2, "visited")]
        got = pick_next_vacancy(items, items[1].url)
        assert got and got.url == items[0].url

    def test_does_not_stuck_on_same_when_other_new_exists(self):
        items = [_v(1, "new"), _v(2, "new"), _v(3, "new")]
        a = pick_next_vacancy(items, "")
        assert a and a.url == items[0].url
        a.status = "visited"
        b = pick_next_vacancy(items, a.url)
        assert b and b.url == items[1].url
        b.status = "visited"
        c = pick_next_vacancy(items, b.url)
        assert c and c.url == items[2].url

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
        store.items = [_v(1, "new"), _v(2, "new")]
        store.save()

        first = store.open_next()
        assert first and first.url.endswith("/1001")
        first.status = "visited"
        store.set_active(first.url)

        second = store.open_next()
        assert second and second.url.endswith("/1002")
        assert second.url != first.url

        raw = json.loads(q.read_text(encoding="utf-8"))
        assert raw["active_url"].endswith("/1001")

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
        assert not store.known(a.url) is False  # still known via seen
        assert store.known(a.url)


class TestCoverLetter:
    def test_local_letter_has_contacts_and_no_score_leak(self):
        letter, src = make_cover_letter(
            "Vue Developer",
            company="TestCo",
            description="Need Vue 3 TypeScript remote",
            salary="160000",
            reasons=["+25 Vue 3", "+20 remote", "Score: 87%", "Why:"],
            force_local=True,
        )
        assert src == "local"
        assert "gh0st0fwar.github.io" in letter
        assert "@daniil_virin" in letter
        assert "39dv@mail.ru" in letter
        assert "Vue Developer" in letter
        assert "\u0417\u0434\u0440\u0430\u0432\u0441\u0442\u0432\u0443\u0439\u0442\u0435!" in letter
        assert "Score:" not in letter
        assert "+25 Vue 3" not in letter
        assert "Why:" not in letter


class TestHotkeyBusySemantics:
    def test_pick_sequence_matches_user_flow(self):
        items = [_v(10, "new"), _v(20, "new"), _v(30, "new")]
        active = ""
        opened = []
        for _ in range(3):
            v = pick_next_vacancy(items, active)
            assert v is not None
            opened.append(v.url)
            v.status = "visited"
            active = v.url
        assert opened == [items[0].url, items[1].url, items[2].url]
        again = pick_next_vacancy(items, active)
        assert again and again.url == items[0].url
