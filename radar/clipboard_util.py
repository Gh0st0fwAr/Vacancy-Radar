# -*- coding: utf-8 -*-
"""Reliable Windows clipboard helpers (fast path first)."""
from __future__ import annotations

import subprocess
import threading
import time


def set_clipboard(text: str) -> bool:
    """
    Put text on clipboard. Prefers WinAPI / clip.exe; PowerShell only as last resort
    (cold PowerShell can take several seconds and must not block Chrome open).
    """
    text = text or ""
    if not text:
        return False

    if _via_winapi(text):
        return True
    if _via_clip_exe(text):
        return True
    # Slow path — never call this on the UI critical path if avoidable.
    return _via_powershell(text)


def set_clipboard_async(text: str) -> None:
    """Fire-and-forget clipboard write (does not block UI / Chrome)."""
    threading.Thread(target=lambda: set_clipboard(text or ""), daemon=True).start()


def _via_winapi(text: str) -> bool:
    try:
        import ctypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        CF_UNICODETEXT = 13
        GMEM_MOVEABLE = 0x0002
        data = text.encode("utf-16-le") + b"\x00\x00"
        for _ in range(6):
            if user32.OpenClipboard(None):
                try:
                    user32.EmptyClipboard()
                    h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
                    if not h:
                        continue
                    p = kernel32.GlobalLock(h)
                    ctypes.memmove(p, data, len(data))
                    kernel32.GlobalUnlock(h)
                    if user32.SetClipboardData(CF_UNICODETEXT, h):
                        return True
                finally:
                    user32.CloseClipboard()
            time.sleep(0.02)
    except Exception:
        return False
    return False


def _via_clip_exe(text: str) -> bool:
    try:
        subprocess.run(
            ["clip"],
            input=text.encode("utf-16-le"),
            check=False,
            timeout=0.8,
            capture_output=True,
        )
        return True
    except Exception:
        return False


def _via_powershell(text: str) -> bool:
    try:
        p = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NoLogo",
                "-Command",
                "Set-Clipboard -Value $input",
            ],
            input=text,
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=2,
        )
        return p.returncode == 0
    except Exception:
        return False
