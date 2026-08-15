# -*- coding: utf-8 -*-
"""Vacancy list card delegate matching reference 04 layout."""
from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from radar import theme as theme_mod
from radar.queue_style import ICON_SIZE, STATUS_KIND_ROLE, colors_for_kind

ACTIVE_ROLE = Qt.UserRole + 1
TITLE_ROLE = Qt.UserRole + 4
COMPANY_ROLE = Qt.UserRole + 5
META_ROLE = Qt.UserRole + 6
SCORE_ROLE = Qt.UserRole + 7
PILL_ROLE = Qt.UserRole + 8

CARD_H = 78
STRIPE_W = 5
RADIUS = 10


def pill_colors(kind: str):
    t = theme_mod
    if kind == "pointer":
        return QColor(t.POINTER_BG), QColor(t.POINTER_FG)
    if kind == "invite":
        return QColor(t.INVITE_BG), QColor(t.INVITE)
    if kind == "apply":
        return QColor(t.GRAY_APPLY_BG), QColor(t.GRAY_APPLY)
    if kind == "new":
        return QColor(30, 55, 50), QColor(t.ACCENT)
    if kind == "skipped":
        return QColor(60, 50, 20), QColor(t.WARN)
    return QColor(t.BG_ELEVATED), QColor(t.TEXT_DIM)


class VacancyCardDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QSize(option.rect.width(), CARD_H)

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        rect = option.rect.adjusted(6, 3, -6, -3)
        kind = str(index.data(STATUS_KIND_ROLE) or "other")
        fg, bg, stripe = colors_for_kind(kind)
        selected = bool(option.state & QStyle.State_Selected)
        active = bool(index.data(ACTIVE_ROLE))

        # Card fill
        if bg.alpha() > 0:
            fill = QColor(bg)
            if selected:
                fill = QColor(theme_mod.ACCENT)
                fill.setAlpha(40)
            painter.setBrush(fill)
        elif selected:
            fill = QColor(theme_mod.ACCENT)
            fill.setAlpha(35)
            painter.setBrush(fill)
        else:
            painter.setBrush(QColor(theme_mod.BG_PANEL))

        pen = QPen(QColor(theme_mod.BORDER_SOFT))
        if selected or active:
            pen = QPen(QColor(theme_mod.ACCENT))
            pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, RADIUS, RADIUS)

        # Left status stripe inside card
        stripe_r = QRect(rect.left() + 1, rect.top() + 8, STRIPE_W, rect.height() - 16)
        painter.setPen(Qt.NoPen)
        painter.setBrush(stripe)
        painter.drawRoundedRect(stripe_r, 2, 2)

        x = rect.left() + STRIPE_W + 12
        mid_y = rect.center().y()

        # Icon tile
        icon = index.data(Qt.DecorationRole)
        tile = QRect(x, mid_y - 22, 44, 44)
        painter.setBrush(QColor(theme_mod.BG_ELEVATED))
        painter.setPen(QPen(QColor(theme_mod.BORDER_SOFT)))
        painter.drawRoundedRect(tile, 8, 8)
        if isinstance(icon, QIcon) and not icon.isNull():
            icon.paint(painter, tile.adjusted(4, 4, -4, -4))
        x = tile.right() + 12

        # Score (right)
        score = index.data(SCORE_ROLE)
        score_w = 56
        score_rect = QRect(rect.right() - score_w - 10, rect.top() + 8, score_w, rect.height() - 16)
        if score is not None and int(score) > 0:
            sf = QFont(option.font)
            sf.setBold(True)
            sf.setPixelSize(22)
            painter.setFont(sf)
            painter.setPen(QColor(theme_mod.ACCENT))
            painter.drawText(score_rect, int(Qt.AlignVCenter | Qt.AlignRight), str(int(score)))

        # Pill (left of score)
        pill = str(index.data(PILL_ROLE) or "")
        pill_w = 0
        if pill:
            pf = QFont(option.font)
            pf.setBold(True)
            pf.setPixelSize(11)
            painter.setFont(pf)
            tw = painter.fontMetrics().horizontalAdvance(pill) + 16
            pill_w = tw
            pill_rect = QRect(score_rect.left() - tw - 10, mid_y - 12, tw, 24)
            pbg, pfg = pill_colors(kind)
            painter.setPen(Qt.NoPen)
            painter.setBrush(pbg)
            painter.drawRoundedRect(pill_rect, 6, 6)
            painter.setPen(pfg)
            painter.drawText(pill_rect, int(Qt.AlignCenter), pill)

        text_right = score_rect.left() - pill_w - 18
        text_w = max(40, text_right - x)

        title = str(index.data(TITLE_ROLE) or index.data(Qt.DisplayRole) or "")
        company = str(index.data(COMPANY_ROLE) or "")
        meta = str(index.data(META_ROLE) or "")

        tf = QFont(option.font)
        tf.setBold(True)
        tf.setPixelSize(15)
        painter.setFont(tf)
        painter.setPen(fg if fg.isValid() else QColor(theme_mod.TEXT))
        title_rect = QRect(x, rect.top() + 10, text_w, 22)
        painter.drawText(
            title_rect,
            int(Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine),
            painter.fontMetrics().elidedText(title, Qt.ElideRight, text_w),
        )

        cf = QFont(option.font)
        cf.setPixelSize(13)
        painter.setFont(cf)
        painter.setPen(QColor(theme_mod.ACCENT))
        company_rect = QRect(x, title_rect.bottom() + 1, text_w, 18)
        painter.drawText(
            company_rect,
            int(Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine),
            painter.fontMetrics().elidedText(company, Qt.ElideRight, text_w),
        )

        mf = QFont(option.font)
        mf.setPixelSize(12)
        painter.setFont(mf)
        painter.setPen(QColor(theme_mod.TEXT_MUTED))
        meta_rect = QRect(x, company_rect.bottom(), text_w, 16)
        painter.drawText(
            meta_rect,
            int(Qt.AlignLeft | Qt.AlignVCenter | Qt.TextSingleLine),
            painter.fontMetrics().elidedText(meta, Qt.ElideRight, text_w),
        )

        painter.restore()
