# -*- coding: utf-8 -*-
"""Patch ui.py for hybrid layout. ASCII-only source; Russian via unicode escapes."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
path = ROOT / "radar" / "ui.py"
text = path.read_text(encoding="utf-8")


def R(s: str) -> str:
    """Decode \\uXXXX sequences in a normal string (already unicode-escaped in source)."""
    return s.encode("utf-8").decode("unicode_escape") if "\\u" in s else s


# --- 1) imports ---
old_imp = """from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)"""

new_imp = """from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)"""
if old_imp not in text:
    raise SystemExit("imports missing")
text = text.replace(old_imp, new_imp, 1)

# --- 2) mid block ---
start = text.find("from radar.queue_style import")
end = text.find("\ndef log(")
if start < 0 or end < 0:
    raise SystemExit("mid markers missing")

new_mid = """from radar.autostart import is_autostart_enabled, set_autostart
from radar.queue_style import (
    ICON_SIZE,
    STATUS_KIND_ROLE,
    colors_for_kind,
    icon_for,
    is_blue,
    status_kind,
)
from radar.stats_hh import fetch_stats
from radar import theme as theme_mod
from radar.theme import (
    ScaleButton,
    THEME_LABELS,
    apply_app_font,
    apply_theme,
)
from radar.themes import THEME_IDS

ACTIVE_ROLE = Qt.UserRole + 1
HH_HIGHLIGHT_ROLE = Qt.UserRole + 2
STRIPE_W = 10


class StatusListDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        rect = option.rect.adjusted(2, 1, -2, -1)
        kind = index.data(STATUS_KIND_ROLE) or "other"
        fg, bg, stripe = colors_for_kind(str(kind))
        if bg.alpha() > 0:
            painter.fillRect(rect, bg)
        elif option.state & QStyle.State_Selected:
            painter.fillRect(rect, QColor(theme_mod.ACCENT).darker(220))
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(rect, QColor(60, 70, 80, 80))
        if option.state & QStyle.State_Selected:
            painter.setPen(QColor(theme_mod.ACCENT))
            painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 8, 8)
        stripe_rect = rect.adjusted(0, 2, 0, -2)
        stripe_rect.setWidth(STRIPE_W)
        painter.fillRect(stripe_rect, stripe)
        icon = index.data(Qt.DecorationRole)
        x = rect.left() + STRIPE_W + 10
        y = rect.top()
        h = rect.height()
        if isinstance(icon, QIcon) and not icon.isNull():
            sz = ICON_SIZE
            iy = y + max(0, (h - sz.height()) // 2)
            icon.paint(painter, x, iy, sz.width(), sz.height())
            x += sz.width() + 10
        else:
            x += 4
        text_s = index.data(Qt.DisplayRole) or ""
        font = QFont(option.font)
        item_font = index.data(Qt.FontRole)
        if isinstance(item_font, QFont):
            font = QFont(item_font)
        painter.setFont(font)
        painter.setPen(fg if fg.isValid() else QColor("#e8edf2"))
        text_rect = rect.adjusted(x - rect.left(), 4, -10, -4)
        flags = int(Qt.AlignVCenter | Qt.AlignLeft | Qt.TextWordWrap)
        painter.drawText(text_rect, flags, text_s)
        painter.restore()

    def sizeHint(self, option, index):
        sh = super().sizeHint(option, index)
        sh.setHeight(max(sh.height(), 64))
        return sh


"""
text = text[:start] + new_mid + text[end + 1 :]
text = text.replace("PointerGlowDelegate(self.list)", "StatusListDelegate(self.list)")

# Fix OK/ACCENT/DANGER refs that used direct imports — use theme_mod
for name in ("OK", "ACCENT", "DANGER"):
    text = text.replace(
        f'self.lbl_hk_status.setStyleSheet(f"color: {{{name}}};',
        f'self.lbl_hk_status.setStyleSheet(f"color: {{theme_mod.{name}}};',
    )

path.write_text(text, encoding="utf-8")
compile(text, str(path), "exec")
print("part1 ok", path.stat().st_size)
