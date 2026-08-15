# -*- coding: utf-8 -*-
"""Global hotkey capture/listen via pynput (keyboard + mouse X1/X2)."""
from __future__ import annotations

from typing import Callable, Optional, Set

from pynput import keyboard, mouse


def normalize_hotkey(s: str) -> str:
    s = (s or "").strip().lower().replace(" ", "")
    s = s.replace("control", "ctrl").replace("command", "cmd")
    return s


def hotkey_label(s: str) -> str:
    s = normalize_hotkey(s)
    if s in ("x1", "mousex1", "button.x1"):
        return "Mouse X1 (боковая назад)"
    if s in ("x2", "mousex2", "button.x2"):
        return "Mouse X2 (боковая вперёд)"
    return s.upper().replace("+", " + ")


class HotkeyManager:
    def __init__(self, on_trigger: Callable[[], None]) -> None:
        self.on_trigger = on_trigger
        self.hotkey = "ctrl+alt+q"
        self._kb_listener: Optional[keyboard.Listener] = None
        self._mouse_listener: Optional[mouse.Listener] = None
        self._capture_cb: Optional[Callable[[str], None]] = None
        self._pressed: Set[str] = set()
        self._enabled = True
        self._last_fire = 0.0

    def set_hotkey(self, hk: str) -> None:
        self.hotkey = normalize_hotkey(hk)
        self.restart()

    def start_capture(self, cb: Callable[[str], None]) -> None:
        self._capture_cb = cb

    def cancel_capture(self) -> None:
        self._capture_cb = None

    def start(self) -> None:
        self.stop()
        self._kb_listener = keyboard.Listener(
            on_press=self._on_key_press,
            on_release=self._on_key_release,
        )
        self._mouse_listener = mouse.Listener(on_click=self._on_click)
        self._kb_listener.start()
        self._mouse_listener.start()

    def restart(self) -> None:
        self.start()

    def stop(self) -> None:
        for lst in (self._kb_listener, self._mouse_listener):
            if lst:
                try:
                    lst.stop()
                except Exception:
                    pass
        self._kb_listener = None
        self._mouse_listener = None
        self._pressed.clear()

    def _key_name(self, key) -> Optional[str]:
        mapping = {
            keyboard.Key.ctrl: "ctrl",
            keyboard.Key.ctrl_l: "ctrl",
            keyboard.Key.ctrl_r: "ctrl",
            keyboard.Key.alt: "alt",
            keyboard.Key.alt_l: "alt",
            keyboard.Key.alt_r: "alt",
            keyboard.Key.alt_gr: "alt",
            keyboard.Key.shift: "shift",
            keyboard.Key.shift_l: "shift",
            keyboard.Key.shift_r: "shift",
            keyboard.Key.cmd: "win",
            keyboard.Key.cmd_l: "win",
            keyboard.Key.cmd_r: "win",
            keyboard.Key.space: "space",
            keyboard.Key.enter: "enter",
            keyboard.Key.tab: "tab",
            keyboard.Key.esc: "esc",
        }
        if key in mapping:
            return mapping[key]

        # With Ctrl/Alt, key.char is often None — use virtual-key code
        vk = getattr(key, "vk", None)
        if vk is not None:
            if 65 <= vk <= 90:
                return chr(vk).lower()
            if 48 <= vk <= 57:
                return chr(vk)
            if 96 <= vk <= 105:
                return chr(vk - 96 + ord("0"))
            if 112 <= vk <= 123:
                return f"f{vk - 111}"

        try:
            ch = getattr(key, "char", None)
            if ch and ch.isprintable() and ord(ch) >= 32:
                return ch.lower()
        except Exception:
            pass

        name = str(key).replace("Key.", "").lower()
        if name.startswith("'") and name.endswith("'") and len(name) == 3:
            return name[1]
        if name.startswith("<") and name.endswith(">"):
            try:
                n = int(name[1:-1])
                if 65 <= n <= 90:
                    return chr(n).lower()
            except Exception:
                pass
        return None

    def _combo_from_pressed(self) -> str:
        mods = [m for m in ("ctrl", "alt", "shift", "win") if m in self._pressed]
        keys = [k for k in self._pressed if k not in ("ctrl", "alt", "shift", "win")]
        if not keys:
            return "+".join(mods)
        return "+".join(mods + [keys[-1]])

    def _fire(self) -> None:
        import time

        now = time.time()
        # Антидребезг: иначе Ctrl+Alt+Q успевает открыть несколько вкладок подряд.
        if now - self._last_fire < 1.5:
            return
        self._last_fire = now
        try:
            self.on_trigger()
        except Exception:
            pass

    def _on_key_press(self, key) -> None:
        name = self._key_name(key)
        if not name:
            return
        self._pressed.add(name)
        combo = normalize_hotkey(self._combo_from_pressed())

        if self._capture_cb:
            if name not in ("ctrl", "alt", "shift", "win"):
                cb = self._capture_cb
                self._capture_cb = None
                if combo:
                    cb(combo)
            return

        if not self._enabled:
            return
        if combo == normalize_hotkey(self.hotkey):
            self._fire()

    def _on_key_release(self, key) -> None:
        name = self._key_name(key)
        if name and name in self._pressed:
            self._pressed.discard(name)

    def _on_click(self, x, y, button, pressed) -> None:
        if not pressed:
            return
        name = None
        if button == mouse.Button.x1:
            name = "x1"
        elif button == mouse.Button.x2:
            name = "x2"
        if not name:
            return
        if self._capture_cb:
            cb = self._capture_cb
            self._capture_cb = None
            cb(name)
            return
        if not self._enabled:
            return
        if normalize_hotkey(self.hotkey) == name:
            self._fire()
