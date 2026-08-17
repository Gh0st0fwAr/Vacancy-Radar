# -*- coding: utf-8 -*-
from radar.hotkeys import combo_actually_down, combo_parts
from radar.win_hotkey import MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, parse_win_hotkey


class TestComboMatch:
    def test_alt_q_is_not_ctrl_alt_q(self):
        assert combo_actually_down("ctrl+alt+q", mods_down={"alt"}) is False

    def test_alt_w_is_not_ctrl_alt_q(self):
        assert combo_actually_down("ctrl+alt+q", mods_down={"alt"}) is False

    def test_ctrl_alt_matches(self):
        assert combo_actually_down("ctrl+alt+q", mods_down={"ctrl", "alt"}) is True

    def test_ctrl_only_does_not_match(self):
        assert combo_actually_down("ctrl+alt+q", mods_down={"ctrl"}) is False

    def test_parts(self):
        mods, key = combo_parts("Ctrl + Alt + Q")
        assert mods == {"ctrl", "alt"}
        assert key == "q"


class TestParseWinHotkey:
    def test_ctrl_alt_q(self):
        parsed = parse_win_hotkey("ctrl+alt+q")
        assert parsed is not None
        mods, vk = parsed
        assert mods & MOD_CONTROL
        assert mods & MOD_ALT
        assert mods & MOD_NOREPEAT
        assert vk == ord("Q")
