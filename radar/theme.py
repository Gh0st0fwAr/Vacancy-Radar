# -*- coding: utf-8 -*-
"""Graphite high-contrast theme for VacancyRadar (large type)."""
from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtGui import QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect,
    QPushButton,
    QStyle,
    QStyleOptionButton,
)


BG = "#1c2128"
BG_PANEL = "#252b33"
BG_ELEVATED = "#2e3640"
BG_INPUT = "#181c22"
BORDER = "#4a5562"
BORDER_SOFT = "#3a4450"
TEXT = "#e8edf2"
TEXT_DIM = "#a8b3c0"
TEXT_MUTED = "#7d8a99"
ACCENT = "#6ec8b8"
ACCENT_DIM = "#3d7a70"
DANGER = "#d47878"
OK = "#7bc47f"
WARN = "#e6c35c"


THEME_QSS = f"""
* {{
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 16px;
    color: {TEXT};
}}

QMainWindow, QWidget {{
    background-color: {BG};
    color: {TEXT};
}}

QLabel {{
    color: {TEXT};
    font-size: 16px;
    background: transparent;
}}

QLabel#sectionTitle {{
    font-size: 19px;
    font-weight: 700;
    color: {TEXT};
    padding: 6px 0 10px 0;
}}

QLabel#hotkeyBadge {{
    font-size: 24px;
    font-weight: 700;
    color: {ACCENT};
    padding: 12px 16px;
    background-color: {BG_ELEVATED};
    border: 1px solid {ACCENT_DIM};
    border-radius: 12px;
}}

QLabel#statsValue {{
    font-size: 20px;
    font-weight: 700;
    color: {ACCENT};
}}

QLabel#mutedLabel {{
    font-size: 15px;
    color: {TEXT_MUTED};
}}

QGroupBox {{
    font-size: 18px;
    font-weight: 700;
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 14px;
    margin-top: 18px;
    padding-top: 22px;
    padding-left: 16px;
    padding-right: 16px;
    padding-bottom: 14px;
    background-color: {BG_PANEL};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 16px;
    padding: 0 10px;
    color: {ACCENT};
}}

QScrollArea {{
    background-color: {BG};
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background-color: {BG};
}}

QListWidget {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 10px;
    font-size: 18px;
    outline: none;
}}

QListWidget::item {{
    padding: 14px 16px;
    margin: 4px 2px;
    border-radius: 10px;
    border: 1px solid transparent;
    min-height: 32px;
}}

QListWidget::item:selected {{
    background-color: {ACCENT_DIM};
    border: 1px solid {ACCENT};
    color: {TEXT};
}}

QListWidget::item:hover:!selected {{
    background-color: {BG_ELEVATED};
    border: 1px solid {BORDER};
}}

QTextEdit {{
    background-color: {BG_INPUT};
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 14px;
    font-size: 17px;
    line-height: 1.45;
    selection-background-color: {ACCENT_DIM};
}}

QCheckBox {{
    font-size: 17px;
    spacing: 12px;
    padding: 8px 2px;
    color: {TEXT};
    background: transparent;
}}

QCheckBox::indicator {{
    width: 24px;
    height: 24px;
    border-radius: 7px;
    border: 2px solid {BORDER};
    background: {BG_INPUT};
}}

QCheckBox::indicator:checked {{
    background-color: {ACCENT};
    border-color: {ACCENT};
}}

QCheckBox::indicator:hover {{
    border-color: {ACCENT};
}}

QPushButton {{
    background-color: {BG_ELEVATED};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 14px;
    padding: 14px 20px;
    font-size: 16px;
    font-weight: 600;
    min-height: 26px;
}}

QPushButton:hover {{
    background-color: #3a4452;
    border: 2px solid {ACCENT};
    color: {TEXT};
}}

QPushButton:pressed {{
    background-color: #222830;
    border: 2px solid {ACCENT_DIM};
}}

QPushButton:disabled {{
    background-color: #22262c;
    color: {TEXT_MUTED};
    border-color: {BORDER_SOFT};
}}

QPushButton#primaryBtn {{
    background-color: #2f5f58;
    border: 2px solid {ACCENT};
    color: #f2fffc;
    font-size: 17px;
}}

QPushButton#primaryBtn:hover {{
    background-color: #3a756c;
    border: 2px solid #8fd9cb;
}}

QPushButton#primaryBtn:pressed {{
    background-color: #244842;
}}

QPushButton#okBtn {{
    background-color: #2d4a32;
    border: 2px solid {OK};
}}

QPushButton#okBtn:hover {{
    background-color: #3a5f40;
}}

QPushButton#dangerBtn {{
    background-color: #4a2e2e;
    border: 2px solid {DANGER};
}}

QPushButton#dangerBtn:hover {{
    background-color: #5c3838;
}}

QPushButton#warnBtn {{
    background-color: #4a4020;
    border: 2px solid {WARN};
    color: #fff6d5;
}}

QPushButton#warnBtn:hover {{
    background-color: #5c4f28;
    border: 2px solid #f0d56a;
}}

QPushButton#ghostBtn {{
    background-color: transparent;
    border: 1px dashed {BORDER};
}}

QStatusBar {{
    background-color: {BG_PANEL};
    color: {TEXT_DIM};
    font-size: 15px;
    border-top: 1px solid {BORDER_SOFT};
    padding: 6px 12px;
    min-height: 28px;
}}

QSplitter::handle {{
    background-color: {BORDER_SOFT};
    width: 4px;
    margin: 10px 5px;
    border-radius: 2px;
}}

QScrollBar:vertical {{
    background: {BG};
    width: 18px;
    margin: 2px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background: {BORDER};
    min-height: 48px;
    border-radius: 9px;
    border: 1px solid {BORDER_SOFT};
}}

QScrollBar::handle:vertical:hover {{
    background: {ACCENT_DIM};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background: {BG};
    height: 14px;
    margin: 2px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background: {BORDER};
    min-width: 40px;
    border-radius: 7px;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

QMessageBox {{
    background-color: {BG_PANEL};
}}

QMessageBox QLabel {{
    font-size: 17px;
    color: {TEXT};
    min-width: 420px;
}}

QFormLayout {{
    font-size: 16px;
}}
"""


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
    font = QFont("Segoe UI", 12)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)
