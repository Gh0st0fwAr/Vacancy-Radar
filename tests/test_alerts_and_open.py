# -*- coding: utf-8 -*-
"""Tests: alerts, open-fast path, sounds helpers."""
from __future__ import annotations

from unittest.mock import patch

from radar.alerts import detect_employer_activity, format_activity_toast
from radar.queue_store import Vacancy
from radar.sounds import sound_allowed


class TestEmployerActivity:
    def test_no_events_on_first_scrape(self):
        prev = {}
        new = {"ok": True, "invitations": 2, "interviews": 1, "unread_messages": 3}
        assert detect_employer_activity(prev, new) == []

    def test_detects_increases(self):
        prev = {"ok": True, "invitations": 1, "interviews": 0, "unread_messages": 0}
        new = {"ok": True, "invitations": 2, "interviews": 1, "unread_messages": 4}
        events = detect_employer_activity(prev, new)
        kinds = {e["kind"] for e in events}
        assert kinds == {"invitations", "interviews", "unread_messages"}
        inv = next(e for e in events if e["kind"] == "invitations")
        assert inv["from"] == 1 and inv["to"] == 2 and inv["delta"] == 1

    def test_ignores_decrease_and_flat(self):
        prev = {"ok": True, "invitations": 5, "unread_messages": 2}
        new = {"ok": True, "invitations": 4, "unread_messages": 2}
        assert detect_employer_activity(prev, new) == []

    def test_ignores_failed_scrape(self):
        prev = {"ok": True, "invitations": 1}
        new = {"ok": False, "invitations": 9}
        assert detect_employer_activity(prev, new) == []

    def test_toast_format(self):
        text = format_activity_toast(
            [{"label": "Invite", "from": 1, "to": 2, "kind": "invitations", "delta": 1}]
        )
        assert "1" in text and "2" in text


class TestSoundAllowed:
    def test_respects_flags(self):
        assert sound_allowed({"sound_enabled": True, "dnd": False})
        assert not sound_allowed({"sound_enabled": False, "dnd": False})
        assert not sound_allowed({"sound_enabled": True, "dnd": True})


class TestOpenUrlFast:
    def test_prefers_short_put_encoded(self):
        from radar import chrome_ctl

        calls = []

        def fake_http(url, method="GET", timeout=1.0):
            calls.append((method, timeout, "encoded" in url or "%3A" in url))
            return {"id": "1"}

        with patch.object(chrome_ctl, "_port_open", return_value=True):
            with patch.object(chrome_ctl, "_http_json", side_effect=fake_http):
                with patch.object(chrome_ctl, "_bring_chrome_forward"):
                    ok = chrome_ctl.open_url_fast("https://hh.ru/vacancy/1")
        assert ok is True
        assert calls
        assert calls[0][0] == "PUT"
        assert calls[0][1] <= 0.4


class TestOpenVacancyFast:
    def test_order_open_then_clipboard(self):
        from radar import search_hh

        order = []
        v = Vacancy(
            id="1",
            title="Vue Dev",
            company="Co",
            url="https://hh.ru/vacancy/999",
            score=80,
            cover_letter="letter body",
        )

        with patch(
            "radar.search_hh.open_url_fast",
            side_effect=lambda url, port=None: order.append("open") or True,
        ):
            with patch(
                "radar.clipboard_util.set_clipboard",
                side_effect=lambda text: order.append("clip") or True,
            ):
                result = search_hh.open_vacancy_and_prepare(v)

        assert result["ok"]
        assert result["clicked"] is False
        assert result["pasted"] is False
        assert order == ["open", "clip"]

    def test_pending_letter_skips_clipboard(self):
        from radar import search_hh

        order = []
        v = Vacancy(
            id="1",
            title="Vue Dev",
            company="Co",
            url="https://hh.ru/vacancy/1001",
            score=80,
            cover_letter="",
        )
        with patch(
            "radar.search_hh.open_url_fast",
            side_effect=lambda *a, **k: order.append("open") or True,
        ):
            with patch(
                "radar.clipboard_util.set_clipboard",
                side_effect=lambda text: order.append("clip") or True,
            ):
                result = search_hh.open_vacancy_and_prepare(v)
        assert result["ok"]
        assert result.get("letter_pending") is True
        assert order == ["open"]
        assert result["clipboard"] is False
