# -*- coding: utf-8 -*-
"""Tests for QueueStore status guard (no illegal downgrades)."""
from __future__ import annotations

from radar.queue_store import QueueStore, Vacancy


def _store(*items: Vacancy) -> QueueStore:
    s = QueueStore(autoload=False)
    s.items = list(items)
    s.seen = {v.url for v in items if v.url}
    return s


class TestStatusGuard:
    def test_applied_cannot_become_new(self):
        v = Vacancy(id="1", title="X", company="C", url="https://hh.ru/vacancy/1", score=80, status="applied")
        store = _store(v)
        store.mark("https://hh.ru/vacancy/1", "new")
        assert store.items[0].status == "applied"

    def test_applied_cannot_become_visited(self):
        v = Vacancy(id="1", title="X", company="C", url="https://hh.ru/vacancy/1", score=80, status="applied")
        store = _store(v)
        store.mark("https://hh.ru/vacancy/1", "visited")
        assert store.items[0].status == "applied"

    def test_visited_cannot_become_new(self):
        v = Vacancy(id="1", title="X", company="C", url="https://hh.ru/vacancy/1", score=80, status="visited")
        store = _store(v)
        store.mark("https://hh.ru/vacancy/1", "new")
        assert store.items[0].status == "visited"

    def test_new_can_become_visited(self):
        v = Vacancy(id="1", title="X", company="C", url="https://hh.ru/vacancy/1", score=80, status="new")
        store = _store(v)
        store.mark("https://hh.ru/vacancy/1", "visited")
        assert store.items[0].status == "visited"

    def test_visited_can_become_applied(self):
        v = Vacancy(id="1", title="X", company="C", url="https://hh.ru/vacancy/1", score=80, status="visited")
        store = _store(v)
        store.mark("https://hh.ru/vacancy/1", "applied")
        assert store.items[0].status == "applied"

    def test_new_can_become_applied(self):
        v = Vacancy(id="1", title="X", company="C", url="https://hh.ru/vacancy/1", score=80, status="new")
        store = _store(v)
        store.mark("https://hh.ru/vacancy/1", "applied")
        assert store.items[0].status == "applied"

    def test_banned_removes_from_queue(self):
        v = Vacancy(id="1", title="X", company="C", url="https://hh.ru/vacancy/1", score=80, status="applied")
        store = _store(v)
        store.mark("https://hh.ru/vacancy/1", "banned")
        assert len(store.items) == 0
        assert "https://hh.ru/vacancy/1" in store.seen

    def test_add_does_not_duplicate(self):
        existing = Vacancy(id="1", title="X", company="C", url="https://hh.ru/vacancy/1", score=80, status="applied")
        store = _store(existing)
        duplicate = Vacancy(id="1", title="X new", company="C", url="https://hh.ru/vacancy/1", score=90, status="new")
        added = store.add(duplicate)
        assert added is False
        assert len(store.items) == 1
        assert store.items[0].status == "applied"
