# -*- coding: utf-8 -*-
"""Cursor cover letters must be unique per vacancy (no universal local on cursor branch)."""
from __future__ import annotations

from unittest.mock import patch

from radar.cover_letter import make_cover_letter
from radar.queue_store import QueueStore, Vacancy
from radar.search_hh import upgrade_cover_letters


def test_upgrade_uses_cursor_not_local_when_pending(tmp_path, monkeypatch):
    store = QueueStore.__new__(QueueStore)
    store.path = tmp_path / "q.json"
    store.items = [
        Vacancy(
            id="1",
            title="Vue 3 Middle remote",
            company="Co",
            url="https://hh.ru/vacancy/111",
            score=80,
            reasons=["+25 Vue"],
            salary="160000",
            cover_letter="",
            letter_source="pending",
            description=(
                "Full vacancy text: Vue 3, TypeScript, Pinia, dashboards, "
                "Ag-Grid, remote only, Middle. Unique marker ALPHA42."
            ),
            status="new",
        )
    ]
    store.seen = set()
    store.pointer = 0
    store.active_url = ""
    store.save = lambda: None  # type: ignore

    cfg = {
        "python_only": False,
        "cover_letter_via_cursor": True,
        "cursor_api_key": "test-key",
        "cursor_model": "composer-2.5",
    }

    def fake_make(title, **kwargs):
        assert "ALPHA42" in (kwargs.get("description") or "")
        assert kwargs.get("force_local") is False
        return (
            "?????????: https://gh0st0fwar.github.io/\n"
            "Telegram: @daniil_virin\n"
            "Email: 39dv@mail.ru\n\n"
            "????????????!\n"
            f"?????????????? ???? ???????? {title}.\n"
            "Unique Cursor letter mentioning ALPHA42 and Vue 3 dashboards.\n"
            + ("x" * 200),
            "cursor",
        )

    with patch("radar.search_hh.load_config", return_value=cfg):
        with patch("radar.cover_letter._api_key", return_value="test-key"):
            with patch("radar.search_hh.make_cover_letter", side_effect=fake_make):
                n = upgrade_cover_letters(store)

    assert n == 1
    assert store.items[0].letter_source == "cursor"
    assert "ALPHA42" in store.items[0].cover_letter
    assert "NMS ??? ???????" not in store.items[0].cover_letter


def test_make_cover_letter_prefers_cursor_when_not_python_only():
    cfg = {
        "python_only": False,
        "cover_letter_via_cursor": True,
        "cursor_api_key": "k",
        "cursor_model": "composer-2.5",
    }
    with patch("radar.cover_letter.load_config", return_value=cfg):
        with patch(
            "radar.cover_letter._via_cursor",
            return_value=(
                "?????????: https://gh0st0fwar.github.io/\nTelegram: @daniil_virin\n"
                "Email: 39dv@mail.ru\n\n????????????!\n"
                + ("Cursor unique body " * 40),
                {"elapsed_ms": 10, "usage": None},
            ),
        ):
            letter, src = make_cover_letter(
                "Nuxt 3",
                description="Full Nuxt SSR text UNIQUE99",
                force_local=False,
            )
    assert src == "cursor"
    assert "Cursor unique" in letter
