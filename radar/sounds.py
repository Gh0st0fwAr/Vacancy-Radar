# -*- coding: utf-8 -*-
from __future__ import annotations

import threading
from typing import Callable, Optional


def _beep_loop(count: int, freq: int = 880, dur: int = 160, gap: float = 0.05) -> None:
    def _run():
        try:
            import time
            import winsound

            for i in range(count):
                winsound.Beep(freq, dur)
                if i + 1 < count and gap:
                    time.sleep(gap)
        except Exception:
            try:
                print("\a" * count, flush=True)
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()


def beep_once() -> None:
    """Хоткей услышан / вкладка открывается."""
    _beep_loop(1, freq=980, dur=140)


def beep_double() -> None:
    """Письмо готово и положено в буфер."""
    _beep_loop(2, freq=1100, dur=150, gap=0.08)


def beep_triple() -> None:
    """Новые вакансии в очереди."""
    def _run():
        try:
            import winsound

            for _ in range(3):
                winsound.Beep(880, 180)
                winsound.Beep(1175, 180)
        except Exception:
            try:
                print("\a\a\a", flush=True)
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()


def beep_six() -> None:
    """Активность работодателя (приглашение / чат / собес)."""
    _beep_loop(6, freq=1200, dur=120, gap=0.06)


def sound_allowed(cfg: Optional[dict], *, check: Optional[Callable[[], bool]] = None) -> bool:
    cfg = cfg or {}
    if not cfg.get("sound_enabled", True):
        return False
    if cfg.get("dnd"):
        return False
    if check is not None and not check():
        return False
    return True
