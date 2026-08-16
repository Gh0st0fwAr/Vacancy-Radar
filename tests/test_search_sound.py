# -*- coding: utf-8 -*-
"""Auto and manual search share the same sound path."""
from __future__ import annotations

from unittest.mock import patch

from radar.sounds import announce_search, sound_allowed


class TestAnnounceSearch:
    def test_zero_added_still_beeps_search_done(self):
        with patch("radar.sounds.beep_search_done") as done:
            with patch("radar.sounds.beep_triple") as triple:
                msg = announce_search({"sound_enabled": True, "dnd": False}, 0)
        assert msg is not None
        assert "search" in msg.lower() or "\u043f\u043e\u0438\u0441\u043a" in msg
        done.assert_called_once()
        triple.assert_not_called()

    def test_added_triggers_triple(self):
        with patch("radar.sounds.beep_search_done") as done:
            with patch("radar.sounds.beep_triple") as triple:
                msg = announce_search({"sound_enabled": True, "dnd": False}, 2)
        assert msg is not None
        assert "2" in msg
        done.assert_called_once()
        triple.assert_called_once()

    def test_muted_by_dnd_or_flag(self):
        with patch("radar.sounds.beep_search_done") as done:
            assert announce_search({"sound_enabled": False, "dnd": False}, 1) is None
            assert announce_search({"sound_enabled": True, "dnd": True}, 1) is None
        done.assert_not_called()


class TestTimerUsesSameSearchEntry:
    def test_search_timer_connected_to_run_search(self):
        """Regression: auto mode must call the same run_search as F5."""
        import inspect
        from radar import ui as ui_mod

        src = inspect.getsource(ui_mod.MainWindow.__init__)
        assert "search_timer.timeout.connect(self.run_search)" in src
        done_src = inspect.getsource(ui_mod.MainWindow._on_search_done)
        assert "announce_search" in done_src


class TestSoundAllowed:
    def test_flags(self):
        assert sound_allowed({"sound_enabled": True, "dnd": False})
        assert not sound_allowed({"sound_enabled": False})
