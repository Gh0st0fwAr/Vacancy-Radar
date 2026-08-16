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


def beep_search_done() -> None:
    """
    Успешный тик поиска (таймер и «Искать сейчас»).
    Заметнее короткого клика: две ноты вверх, ~0.35с — слышно из трея.
    """
    def _run():
        try:
            import time
            import winsound

            winsound.Beep(587, 120)  # D5
            time.sleep(0.05)
            winsound.Beep(880, 160)  # A5
        except Exception:
            try:
                print("\a", flush=True)
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()


def beep_six() -> None:
    """Активность работодателя (приглашение / чат / собес)."""
    _beep_loop(6, freq=1200, dur=120, gap=0.06)


def announce_search(cfg: Optional[dict], n_added: int = 0) -> Optional[str]:
    """
    Sound after a successful search tick (timer or manual).
    Always chirp when sound is on; triple only if new vacancies were added.
    Returns a short log line, or None if muted.
    """
    if not sound_allowed(cfg):
        return None
    beep_search_done()
    if n_added > 0:
        beep_triple()
        return f"Звук: поиск завершён (+тройной: новых {n_added})"
    return "Звук: поиск завершён"


def sound_allowed(cfg: Optional[dict], *, check: Optional[Callable[[], bool]] = None) -> bool:
    cfg = cfg or {}
    if not cfg.get("sound_enabled", True):
        return False
    if cfg.get("dnd"):
        return False
    if check is not None and not check():
        return False
    return True
