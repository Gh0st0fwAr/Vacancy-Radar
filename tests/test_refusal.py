# -*- coding: utf-8 -*-
"""Tests for HH refusal detection and hotkey skip."""
from __future__ import annotations

import json

from radar.refusal import text_looks_like_refusal, vacancy_looks_refused
from radar.queue_store import QueueStore, Vacancy, is_hotkey_white, pick_next_vacancy
from radar.scorer import score_vacancy


class TestRefusalText:
    def test_detects_vam_otkazali(self):
        assert text_looks_like_refusal("...\n\u0412\u0430\u043c \u043e\u0442\u043a\u0430\u0437\u0430\u043b\u0438\n\u0427\u0430\u0442\n...")

    def test_ignores_clean(self):
        assert not text_looks_like_refusal("Vue 3 TypeScript remote Middle")


class TestVacancyLooksRefused:
    def test_from_description(self):
        v = Vacancy(
            id="1",
            title="Vue",
            company="Co",
            url="https://hh.ru/vacancy/135484320",
            score=80,
            status="visited",
            description="\u0421\u0435\u0439\u0447\u0430\u0441 \u0441\u043c\u043e\u0442\u0440\u044f\u0442 6 \u0447\u0435\u043b\u043e\u0432\u0435\u043a\n\u0412\u0430\u043c \u043e\u0442\u043a\u0430\u0437\u0430\u043b\u0438\n\u041e\u0442\u043a\u043b\u0438\u043a \u0434\u0440\u0443\u0433\u0438\u043c \u0440\u0435\u0437\u044e\u043c\u0435",
        )
        assert vacancy_looks_refused(v)
        assert not is_hotkey_white(v)

    def test_from_hh_status_discard(self):
        v = Vacancy(
            id="1",
            title="Vue",
            company="Co",
            url="https://hh.ru/vacancy/1",
            score=80,
            hh_status="discard",
        )
        assert vacancy_looks_refused(v)


class TestPurgeRefused:
    def test_removes_and_keeps_seen(self, tmp_path, monkeypatch):
        monkeypatch.setattr("radar.queue_store.QUEUE_PATH", tmp_path / "q.json")
        monkeypatch.setattr("radar.queue_store.SEEN_PATH", tmp_path / "s.json")
        (tmp_path / "q.json").write_text(
            json.dumps({"items": [], "pointer": 0, "active_url": ""}), encoding="utf-8"
        )
        (tmp_path / "s.json").write_text("[]", encoding="utf-8")

        store = QueueStore(autoload=True)
        bad = Vacancy(
            id="bad",
            title="Bad",
            company="X",
            url="https://hh.ru/vacancy/135484320",
            score=81,
            status="visited",
            description="\u0412\u0430\u043c \u043e\u0442\u043a\u0430\u0437\u0430\u043b\u0438",
            found_at="2026-08-15T14:00:00+00:00",
        )
        good = Vacancy(
            id="good",
            title="Good",
            company="Y",
            url="https://hh.ru/vacancy/999",
            score=80,
            status="new",
            found_at="2026-08-15T13:00:00+00:00",
        )
        store.items = [bad, good]
        store.seen.add(bad.url)
        store.seen.add(good.url)
        store.active_url = bad.url
        n = store.purge_refused()
        assert n == 1
        assert len(store.items) == 1
        assert store.items[0].url.endswith("/999")
        assert bad.url in store.seen
        assert store.active_url == ""
        got = pick_next_vacancy(store.items, "")
        assert got and got.url.endswith("/999")


class TestScorerRefusal:
    def test_rejects_refused_page(self):
        sc, reasons, ok = score_vacancy(
            "Vue Developer",
            "\u0443\u0434\u0430\u043b\u0451\u043d\u043d\u043e Vue 3 TypeScript\n\u0412\u0430\u043c \u043e\u0442\u043a\u0430\u0437\u0430\u043b\u0438\n\u0427\u0430\u0442",
        )
        assert not ok
        assert sc == 0
        assert any("refusal" in r.lower() for r in reasons)


class TestHotkeyBusyIgnoresSecond:
    def test_busy_flag_semantics(self):
        # Mirrors ui.on_hotkey: if busy_open, do not open again.
        busy_open = True
        opened = []

        def on_hotkey():
            if busy_open:
                return
            opened.append(1)

        on_hotkey()
        assert opened == []
        busy_open = False
        on_hotkey()
        assert opened == [1]
