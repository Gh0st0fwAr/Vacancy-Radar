# -*- coding: utf-8 -*-
"""Tests: negotiations mapping, apply, highlight badges."""
from __future__ import annotations

from radar.negotiations_hh import (
    HIGHLIGHT_HH,
    apply_negotiations,
    badge_for,
    normalize_item,
    soft_company,
    status_from_tags,
    title_company_key,
)
from radar.queue_store import QueueStore, Vacancy


def _store(*items: Vacancy) -> QueueStore:
    s = QueueStore(autoload=False)
    s.items = list(items)
    s.seen = {v.url for v in items if v.url}
    return s


class TestStatusFromTags:
    def test_chat_from_employer_reply(self):
        assert status_from_tags("", "", employer_reply=True) == "chat"
        assert "chat" in HIGHLIGHT_HH

    def test_interview_from_qa(self):
        assert (
            status_from_tags("negotiations-tag negotiations-item-interview", "x")
            == "interview"
        )

    def test_discard_from_qa(self):
        assert status_from_tags("negotiations-tag negotiations-item-discard", "") == "discard"

    def test_invitation_from_text(self):
        assert status_from_tags("", "\u041f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u0435") == "invitation"

    def test_not_viewed_is_awaiting(self):
        assert (
            status_from_tags("negotiations-tag negotiations-item-not-viewed", "\u041d\u0435 \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0435\u043d")
            == "awaiting"
        )

    def test_viewed_is_awaiting(self):
        assert status_from_tags("negotiations-tag negotiations-item-viewed", "") == "awaiting"

    def test_filter_fallback(self):
        assert status_from_tags("", "", "archived") == "archived"


class TestNormalizeItem:
    def test_vacancy_href_from_spb_link(self):
        item = normalize_item(
            {
                "title": "Vue Dev",
                "company": "Acme",
                "href": "https://spb.hh.ru/vacancy/999001?hhtmFrom=negotiation_list",
                "tag_qa": "negotiations-tag negotiations-item-interview",
                "tag": "\u0421\u043e\u0431\u0435\u0441\u0435\u0434\u043e\u0432\u0430\u043d\u0438\u0435",
            }
        )
        assert item is not None
        assert item["url"] == "https://hh.ru/vacancy/999001"
        assert item["hh_status"] == "interview"
        assert item["hh_status"] in HIGHLIGHT_HH


class TestSoftCompany:
    def test_strips_ooo_ip(self):
        assert soft_company("\u041e\u041e\u041e \u041d\u0435\u0432\u0430\u0442\u0435\u0445") == soft_company(
            "\u041d\u0435\u0432\u0430\u0442\u0435\u0445"
        )
        assert title_company_key("Full", "\u041e\u041e\u041e \u041d\u0435\u0432\u0430\u0442\u0435\u0445") == title_company_key(
            "Full", "\u041d\u0435\u0432\u0430\u0442\u0435\u0445"
        )


class TestApplyHighlightFields:
    def test_interview_sets_hh_status_and_badge(self, tmp_path, monkeypatch):
        from radar import negotiations_hh as nh
        from radar import queue_store as qs

        monkeypatch.setattr(nh, "NEGOTIATIONS_PATH", tmp_path / "n.json")
        monkeypatch.setattr(qs, "QUEUE_PATH", tmp_path / "q.json")
        monkeypatch.setattr(qs, "SEEN_PATH", tmp_path / "s.json")

        store = _store(
            Vacancy(
                id="1",
                title="UX",
                company="Co",
                url="https://hh.ru/vacancy/136046372",
                score=80,
                status="visited",
            )
        )
        sync = apply_negotiations(
            store,
            [
                {
                    "url": "https://hh.ru/vacancy/136046372",
                    "title": "UX",
                    "company": "Co",
                    "hh_status": "interview",
                    "tag": "\u0421\u043e\u0431\u0435\u0441\u0435\u0434\u043e\u0432\u0430\u043d\u0438\u0435",
                },
                {
                    "url": "https://hh.ru/vacancy/777",
                    "title": "Other",
                    "company": "Y",
                    "hh_status": "awaiting",
                    "tag": "\u041d\u0435 \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0435\u043d",
                },
                {
                    "url": "https://hh.ru/vacancy/888",
                    "title": "Nope",
                    "company": "Z",
                    "hh_status": "discard",
                    "tag": "\u041e\u0442\u043a\u0430\u0437",
                },
            ],
        )
        assert sync["updated"] >= 1
        assert sync["added"] == 1
        assert sync["removed"] == 0
        by_url = {v.url: v for v in store.items}
        assert by_url["https://hh.ru/vacancy/136046372"].hh_status == "interview"
        assert by_url["https://hh.ru/vacancy/136046372"].status == "applied"
        assert "\u0421\u041e\u0411\u0415\u0421" in badge_for(by_url["https://hh.ru/vacancy/136046372"])
        assert by_url["https://hh.ru/vacancy/136046372"].hh_status in HIGHLIGHT_HH
        assert "https://hh.ru/vacancy/777" in by_url
        assert "https://hh.ru/vacancy/888" not in by_url

    def test_removes_discard_match(self, tmp_path, monkeypatch):
        from radar import negotiations_hh as nh
        from radar import queue_store as qs

        monkeypatch.setattr(nh, "NEGOTIATIONS_PATH", tmp_path / "n.json")
        monkeypatch.setattr(qs, "QUEUE_PATH", tmp_path / "q.json")
        monkeypatch.setattr(qs, "SEEN_PATH", tmp_path / "s.json")

        store = _store(
            Vacancy(
                id="1",
                title="Old",
                company="X",
                url="https://hh.ru/vacancy/1",
                score=70,
                status="applied",
            )
        )
        sync = apply_negotiations(
            store,
            [{"url": "https://hh.ru/vacancy/1", "title": "Old", "company": "X", "hh_status": "discard", "tag": "x"}],
        )
        assert sync["removed"] == 1
        assert store.items == []

    def test_company_prefix_match(self, tmp_path, monkeypatch):
        from radar import negotiations_hh as nh
        from radar import queue_store as qs

        monkeypatch.setattr(nh, "NEGOTIATIONS_PATH", tmp_path / "n.json")
        monkeypatch.setattr(qs, "QUEUE_PATH", tmp_path / "q.json")
        monkeypatch.setattr(qs, "SEEN_PATH", tmp_path / "s.json")

        store = _store(
            Vacancy(
                id="1",
                title="Full stack",
                company="\u041e\u041e\u041e\u00a0\u041d\u0435\u0432\u0430\u0442\u0435\u0445",
                url="https://hh.ru/vacancy/134267892",
                score=70,
                status="visited",
            )
        )
        # Match by URL still; also ensure soft key equal
        assert title_company_key("Full stack", "\u041d\u0435\u0432\u0430\u0442\u0435\u0445") == title_company_key(
            "Full stack", store.items[0].company
        )
        apply_negotiations(
            store,
            [
                {
                    "url": "https://hh.ru/vacancy/134267892",
                    "title": "Full stack",
                    "company": "\u041d\u0435\u0432\u0430\u0442\u0435\u0445",
                    "hh_status": "awaiting",
                    "tag": "x",
                }
            ],
        )
        assert store.items[0].hh_status == "awaiting"
        assert store.items[0].status == "applied"

    def test_visited_becomes_applied_on_awaiting(self, tmp_path, monkeypatch):
        from radar import negotiations_hh as nh
        from radar import queue_store as qs

        monkeypatch.setattr(nh, "NEGOTIATIONS_PATH", tmp_path / "n.json")
        monkeypatch.setattr(qs, "QUEUE_PATH", tmp_path / "q.json")
        monkeypatch.setattr(qs, "SEEN_PATH", tmp_path / "s.json")

        store = _store(
            Vacancy(
                id="1",
                title="Vue 3",
                company="FitCo",
                url="https://hh.ru/vacancy/135560619",
                score=90,
                status="visited",
            )
        )
        sync = apply_negotiations(
            store,
            [
                {
                    "url": "https://hh.ru/vacancy/135560619",
                    "title": "Vue 3",
                    "company": "FitCo",
                    "hh_status": "awaiting",
                    "tag": "Не просмотрен",
                }
            ],
        )
        assert sync["promoted"] == 1
        assert store.items[0].status == "applied"
        assert store.items[0].hh_status == "awaiting"


class TestBgTimeoutRaceLogic:
    """Mirrors ui._run_bg done-flag behaviour without Qt."""

    def test_late_ok_after_timeout_still_applies(self):
        done = {"flag": False, "timed_out": False}
        applied = []

        def finish_ok(result):
            if done["flag"] and not done.get("timed_out"):
                return
            done["flag"] = True
            applied.append(result)

        # timeout first
        if not done["flag"]:
            done["timed_out"] = True
            done["flag"] = True
        # late success
        finish_ok({"negotiations": [1, 2, 3]})
        assert applied == [{"negotiations": [1, 2, 3]}]

    def test_double_ok_without_timeout_ignored(self):
        done = {"flag": False, "timed_out": False}
        applied = []

        def finish_ok(result):
            if done["flag"] and not done.get("timed_out"):
                return
            done["flag"] = True
            applied.append(result)

        finish_ok("a")
        finish_ok("b")
        assert applied == ["a"]
