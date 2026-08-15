# -*- coding: utf-8 -*-
"""Theme tokens + ScaleButton. Palettes live in radar.themes."""
from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QPushButton,
    QStyle,
    QStyleOptionButton,
)

from .themes import THEME_IDS, THEME_LABELS, build_qss, get_palette

# Module-level tokens (mutated by apply_theme) — keep import-compat for ui.py
_DEFAULT = get_palette("04")
BG = _DEFAULT["BG"]
BG_PANEL = _DEFAULT["BG_PANEL"]
BG_ELEVATED = _DEFAULT["BG_ELEVATED"]
BG_INPUT = _DEFAULT["BG_INPUT"]
BORDER = _DEFAULT["BORDER"]
BORDER_SOFT = _DEFAULT["BORDER_SOFT"]
TEXT = _DEFAULT["TEXT"]
TEXT_DIM = _DEFAULT["TEXT_DIM"]
TEXT_MUTED = _DEFAULT["TEXT_MUTED"]
ACCENT = _DEFAULT["ACCENT"]
ACCENT_DIM = _DEFAULT["ACCENT_DIM"]
DANGER = _DEFAULT["DANGER"]
OK = _DEFAULT["OK"]
WARN = _DEFAULT["WARN"]
INVITE = _DEFAULT["INVITE"]
INVITE_BG = _DEFAULT["INVITE_BG"]
WHITE_FG = _DEFAULT["WHITE_FG"]
GRAY_APPLY = _DEFAULT["GRAY_APPLY"]
GRAY_APPLY_BG = _DEFAULT["GRAY_APPLY_BG"]
POINTER_FG = _DEFAULT["POINTER_FG"]
POINTER_BG = _DEFAULT["POINTER_BG"]
POINTER_STRIPE = _DEFAULT["POINTER_STRIPE"]
NEW_STRIPE = _DEFAULT["NEW_STRIPE"]
GRAY_STRIPE = _DEFAULT["GRAY_STRIPE"]
WHITE_STRIPE = _DEFAULT["WHITE_STRIPE"]

THEME_QSS = build_qss(_DEFAULT)
_CURRENT_THEME_ID = "04"


def current_theme_id() -> str:
    return _CURRENT_THEME_ID


def apply_theme(app_or_widget, theme_id: str = "04") -> str:
    """Apply palette + QSS. Returns resolved theme id."""
    global BG, BG_PANEL, BG_ELEVATED, BG_INPUT, BORDER, BORDER_SOFT
    global TEXT, TEXT_DIM, TEXT_MUTED, ACCENT, ACCENT_DIM, DANGER, OK, WARN
    global INVITE, INVITE_BG, WHITE_FG, GRAY_APPLY, GRAY_APPLY_BG
    global POINTER_FG, POINTER_BG, POINTER_STRIPE, NEW_STRIPE, GRAY_STRIPE, WHITE_STRIPE
    global THEME_QSS, _CURRENT_THEME_ID

    tid = str(theme_id or "04")
    if tid not in THEME_IDS:
        tid = "04"
    p = get_palette(tid)
    BG = p["BG"]
    BG_PANEL = p["BG_PANEL"]
    BG_ELEVATED = p["BG_ELEVATED"]
    BG_INPUT = p["BG_INPUT"]
    BORDER = p["BORDER"]
    BORDER_SOFT = p["BORDER_SOFT"]
    TEXT = p["TEXT"]
    TEXT_DIM = p["TEXT_DIM"]
    TEXT_MUTED = p["TEXT_MUTED"]
    ACCENT = p["ACCENT"]
    ACCENT_DIM = p["ACCENT_DIM"]
    DANGER = p["DANGER"]
    OK = p["OK"]
    WARN = p["WARN"]
    INVITE = p["INVITE"]
    INVITE_BG = p["INVITE_BG"]
    WHITE_FG = p["WHITE_FG"]
    GRAY_APPLY = p["GRAY_APPLY"]
    GRAY_APPLY_BG = p["GRAY_APPLY_BG"]
    POINTER_FG = p["POINTER_FG"]
    POINTER_BG = p["POINTER_BG"]
    POINTER_STRIPE = p["POINTER_STRIPE"]
    NEW_STRIPE = p["NEW_STRIPE"]
    GRAY_STRIPE = p["GRAY_STRIPE"]
    WHITE_STRIPE = p["WHITE_STRIPE"]
    THEME_QSS = build_qss(p)
    _CURRENT_THEME_ID = tid
    if app_or_widget is not None:
        app_or_widget.setStyleSheet(THEME_QSS)
    return tid


class ScaleButton(QPushButton):
    """Layout-safe visual scale on hover/press (paint transform)."""

    def __init__(self, text: str = "", parent=None, role: str = ""):
        super().__init__(text, parent)
        self._scale = 1.0
        self._anim = QPropertyAnimation(self, b"scale", self)
        self._anim.setDuration(100)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        if role == "primary":
            self.setObjectName("primaryBtn")
        elif role == "ok":
            self.setObjectName("okBtn")
        elif role == "danger":
            self.setObjectName("dangerBtn")
        elif role == "warn":
            self.setObjectName("warnBtn")
        elif role == "ghost":
            self.setObjectName("ghostBtn")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(16)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(0, 0, 0, 140))
        self.setGraphicsEffect(shadow)
        self.setCursor(Qt.PointingHandCursor)

    def get_scale(self) -> float:
        return self._scale

    def set_scale(self, value: float) -> None:
        self._scale = float(value)
        self.update()

    scale = Property(float, get_scale, set_scale)

    def _animate_to(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._scale)
        self._anim.setEndValue(target)
        self._anim.start()

    def enterEvent(self, event) -> None:
        self._animate_to(1.06)
        effect = self.graphicsEffect()
        if isinstance(effect, QGraphicsDropShadowEffect):
            effect.setBlurRadius(26)
            effect.setColor(QColor(110, 200, 184, 120))
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate_to(1.0)
        effect = self.graphicsEffect()
        if isinstance(effect, QGraphicsDropShadowEffect):
            effect.setBlurRadius(16)
            effect.setColor(QColor(0, 0, 0, 140))
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        self._animate_to(0.94)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._animate_to(1.06 if self.underMouse() else 1.0)
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        if abs(self._scale - 1.0) < 0.001:
            super().paintEvent(event)
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.translate(self.width() / 2, self.height() / 2)
        painter.scale(self._scale, self._scale)
        painter.translate(-self.width() / 2, -self.height() / 2)
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        self.style().drawControl(QStyle.CE_PushButton, opt, painter, self)


def apply_app_font(app) -> None:
    from PySide6.QtGui import QFontDatabase

    available = set(QFontDatabase.families())
    family = "Segoe UI"
    for cand in ("Inter", "Cascadia Sans", "Segoe UI Variable Text", "Segoe UI"):
        if cand in available:
            family = cand
            break
    font = QFont(family, 11)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)


__all__ = [
    "THEME_IDS",
    "THEME_LABELS",
    "THEME_QSS",
    "ScaleButton",
    "apply_app_font",
    "apply_theme",
    "current_theme_id",
    "BG",
    "BG_PANEL",
    "TEXT",
    "TEXT_DIM",
    "TEXT_MUTED",
    "ACCENT",
    "ACCENT_DIM",
    "DANGER",
    "OK",
    "WARN",
    "INVITE",
    "INVITE_BG",
    "WHITE_FG",
    "GRAY_APPLY",
    "GRAY_APPLY_BG",
    "POINTER_FG",
    "POINTER_BG",
    "POINTER_STRIPE",
    "NEW_STRIPE",
    "GRAY_STRIPE",
    "WHITE_STRIPE",
]
