# -*- coding: utf-8 -*-
"""Queue row style helpers: white / gray / blue + icons."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPixmap

from . import theme as theme_mod
from .config import ASSETS
from .negotiations_hh import APPLIED_HH, HIGHLIGHT_HH, TERMINAL_HH
from .queue_store import Vacancy

ICON_SIZE = QSize(48, 48)
STATUS_KIND_ROLE = Qt.UserRole + 3


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


def status_kind(v: Vacancy, is_active: bool = False) -> str:
    """Canonical row kind for delegate / colors."""
    if is_active:
        return "pointer"
    if is_blue(v):
        return "invite"
    if is_gray_apply(v):
        return "apply"
    if v.status == "skipped":
        return "skipped"
    if v.status == "visited":
        return "visited"
    if is_white(v) or v.status == "new":
        return "new"
    return "other"


def pill_label(kind: str, v: Optional[Vacancy] = None) -> str:
    """Short status chip text for list cards (no legend needed)."""
    hh = (getattr(v, "hh_status", "") or "") if v is not None else ""
    if kind == "pointer":
        return "NOW"
    if kind == "invite":
        if hh == "interview":
            return "INTERVIEW"
        if hh == "chat":
            return "CHAT"
        if hh == "hired":
            return "OFFER"
        return "INVITE"
    if kind == "apply":
        return "APPLIED"
    if kind == "new":
        return "NEW"
    if kind == "skipped":
        return "SKIP"
    if kind == "visited":
        return "SEEN"
    return ""


LETTER_CHIP = {
    "writing": "…",
    "queued": "WAIT",
    "pending": "WAIT",
    "ok": "OK",
    "cursor": "OK",
    "local": "LOC",
    "fail": "FAIL",
}

LETTER_FACT = {
    "writing": "Writing…",
    "queued": "Queued",
    "pending": "Pending",
    "ok": "Ready",
    "cursor": "Ready",
    "local": "Local",
    "fail": "Failed",
}


def letter_chip(status: str) -> str:
    """Short letter-status chip, analogous to the score column."""
    return LETTER_CHIP.get((status or "").strip().lower(), "")


def letter_fact(status: str) -> str:
    """Detail-pane label for letter generation state."""
    key = (status or "").strip().lower()
    return LETTER_FACT.get(key, status or "?")


def letter_runtime_status(
    v: Vacancy,
    *,
    inflight: Optional[set] = None,
    queued: Optional[set] = None,
) -> str:
    """writing | queued | pending | ok | local | fail | ''."""
    url = getattr(v, "url", "") or ""
    if inflight and url in inflight:
        return "writing"
    if queued and url in queued:
        return "queued"
    src = (getattr(v, "letter_source", "") or "").strip().lower()
    text = (getattr(v, "cover_letter", "") or "").strip()
    if src in ("cursor", "ok") and text:
        return "ok"
    if src == "local" and text:
        return "local"
    if src == "fail":
        return "fail"
    if v.status in ("banned", "skipped", "applied"):
        return "ok" if text else ""
    if src == "pending" or not text:
        return "pending"
    return ""


def colors_for_kind(kind: str) -> Tuple[QColor, QColor, QColor]:
    """Returns (fg, bg, stripe)."""
    t = theme_mod
    if kind == "pointer":
        return QColor(t.POINTER_FG), QColor(t.POINTER_BG), QColor(t.POINTER_STRIPE)
    if kind == "invite":
        return QColor(t.INVITE), QColor(t.INVITE_BG), QColor(t.INVITE)
    if kind == "apply":
        return QColor(t.GRAY_APPLY), QColor(t.GRAY_APPLY_BG), QColor(t.GRAY_STRIPE)
    if kind == "new":
        return QColor(t.WHITE_FG), QColor(0, 0, 0, 0), QColor(t.NEW_STRIPE)
    if kind == "skipped":
        return QColor(t.WARN), QColor(0, 0, 0, 0), QColor(t.WARN)
    if kind == "visited":
        return QColor(t.TEXT_DIM), QColor(0, 0, 0, 0), QColor(t.BORDER_SOFT)
    return QColor(t.TEXT), QColor(0, 0, 0, 0), QColor(t.BORDER)


def icon_kind(v: Vacancy) -> str:
    hh = getattr(v, "hh_status", "") or ""
    if hh == "interview":
        return "interview"
    if hh == "invitation":
        return "invite"
    if hh in ("chat", "hired"):
        return "chat"
    if is_gray_apply(v):
        return "apply"
    return ""


@lru_cache(maxsize=16)
def _icon_path(kind: str) -> Optional[Path]:
    name = {
        "chat": "icon_chat.png",
        "invite": "icon_invite.png",
        "interview": "icon_interview.png",
        "apply": "icon_apply.png",
    }.get(kind)
    if not name:
        return None
    p = ASSETS / name
    return p if p.exists() else None


def clear_icon_cache() -> None:
    _icon_path.cache_clear()


def icon_for(v: Vacancy) -> QIcon:
    kind = icon_kind(v)
    path = _icon_path(kind) if kind else None
    if not path:
        return QIcon()
    pix = QPixmap(str(path))
    if pix.isNull():
        return QIcon()
    return QIcon(pix.scaled(ICON_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation))
