# -*- coding: utf-8 -*-
"""Windows RegisterHotKey — настоящий глобальный хоткей (работает вне окна Radar)."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Callable, Optional

from PySide6.QtCore import QAbstractEventDispatcher, QAbstractNativeEventFilter, QObject

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
HOTKEY_ID = 4242

_VK = {chr(c).lower(): c for c in range(ord("A"), ord("Z") + 1)}
_VK.update({str(d): 0x30 + d for d in range(10)})
_VK.update({f"f{i}": 0x70 + i - 1 for i in range(1, 13)})


def parse_win_hotkey(combo: str) -> Optional[tuple[int, int]]:
    raw = (combo or "").strip().lower().replace(" ", "").replace("control", "ctrl")
    if not raw or raw in ("x1", "x2", "mousex1", "mousex2"):
        return None
    mods = 0
    vk = None
    for part in raw.split("+"):
        if part == "ctrl":
            mods |= MOD_CONTROL
        elif part == "alt":
            mods |= MOD_ALT
        elif part == "shift":
            mods |= MOD_SHIFT
        elif part in ("win", "meta"):
            mods |= MOD_WIN
        elif part in _VK:
            vk = _VK[part]
        else:
            return None
    if vk is None or mods == 0:
        return None
    return mods | MOD_NOREPEAT, vk


class _NativeFilter(QAbstractNativeEventFilter):
    def __init__(self, hotkey_id: int, cb: Callable[[], None]):
        super().__init__()
        self._id = hotkey_id
        self._cb = cb

    def nativeEventFilter(self, eventType, message):
        try:
            et = str(eventType)
            if "windows" not in et:
                return False, 0
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and int(msg.wParam) == self._id:
                self._cb()
        except Exception:
            pass
        return False, 0


class WindowsGlobalHotkey(QObject):
    """RegisterHotKey на HWND окна. Не срабатывает на Alt+Q без Ctrl."""

    def __init__(self, window, combo: str, on_trigger: Callable[[], None]):
        super().__init__(window)
        self._hwnd = int(window.winId())
        self._combo = combo
        self._on_trigger = on_trigger
        self._filter: Optional[_NativeFilter] = None
        self.ok = False

    def start(self) -> bool:
        self.stop()
        parsed = parse_win_hotkey(self._combo)
        if not parsed:
            return False
        mods, vk = parsed
        user32 = ctypes.windll.user32
        if not user32.RegisterHotKey(self._hwnd, HOTKEY_ID, mods, vk):
            return False
        self._filter = _NativeFilter(HOTKEY_ID, self._on_trigger)
        disp = QAbstractEventDispatcher.instance()
        if disp is None:
            user32.UnregisterHotKey(self._hwnd, HOTKEY_ID)
            return False
        disp.installNativeEventFilter(self._filter)
        self.ok = True
        return True

    def stop(self) -> None:
        if self._filter is not None:
            disp = QAbstractEventDispatcher.instance()
            if disp is not None:
                try:
                    disp.removeNativeEventFilter(self._filter)
                except Exception:
                    pass
            self._filter = None
        if self._hwnd:
            try:
                ctypes.windll.user32.UnregisterHotKey(self._hwnd, HOTKEY_ID)
            except Exception:
                pass
        self.ok = False
