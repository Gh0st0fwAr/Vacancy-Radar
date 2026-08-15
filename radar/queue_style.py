# -*- coding: utf-8 -*-
"""Queue row style helpers: white / gray / blue + icons."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QPixmap

from .config import ASSETS
from .negotiations_hh import APPLIED_HH, HIGHLIGHT_HH, TERMINAL_HH
from .queue_store import Vacancy

ICON_SIZE = QSize(48, 48)


def is_blue(v: Vacancy) -> bool:
    """Employer replied (invite / interview / chat / offer), not a refusal."""
    hh = getattr(v, "hh_status", "") or ""
    return hh in HIGHLIGHT_HH


def is_gray_apply(v: Vacancy) -> bool:
    """My application waiting without employer reply."""
    if is_blue(v):
        return False
    hh = getattr(v, "hh_status", "") or ""
    if hh in TERMINAL_HH:
        return False
    if v.status == "applied":
        return True
    if hh in APPLIED_HH or hh == "awaiting":
        return True
    return False


def is_white(v: Vacancy) -> bool:
    """Not applied yet - hotkey targets."""
    if v.status in ("banned", "skipped", "applied"):
        return False
    hh = getattr(v, "hh_status", "") or ""
    if hh in TERMINAL_HH or hh in HIGHLIGHT_HH or hh in APPLIED_HH:
        return False
    return True


def icon_kind(v: Vacancy) -> str:
    hh = getattr(v, "hh_status", "") or ""
    if hh == "interview":
        return "interview"
    if hh == "invitation":
        return "invite"
    if hh in ("chat", "hired"):
        return "chat"
    return ""


@lru_cache(maxsize=8)
def _icon_path(kind: str) -> Optional[Path]:
    name = {
        "chat": "icon_chat.png",
        "invite": "icon_invite.png",
        "interview": "icon_interview.png",
    }.get(kind)
    if not name:
        return None
    p = ASSETS / name
    return p if p.exists() else None


def icon_for(v: Vacancy) -> QIcon:
    kind = icon_kind(v)
    path = _icon_path(kind) if kind else None
    if not path:
        return QIcon()
    pix = QPixmap(str(path))
    if pix.isNull():
        return QIcon()
    return QIcon(pix.scaled(ICON_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation))
