# -*- coding: utf-8 -*-
"""Multi-theme palettes for VacancyRadar (hybrid UI)."""
from __future__ import annotations

from copy import deepcopy
from typing import Dict

THEME_IDS = ("04", "01", "02", "03")
THEME_LABELS = {
    "04": '04 — Hybrid (по умолчанию)',
    "01": '01 — Graphite Split',
    "02": '02 — Compact Pro',
    "03": '03 — Slate Master-Detail',
}

PALETTES: Dict[str, Dict[str, str]] = {'01': {'ACCENT': '#20c997',
        'ACCENT_DIM': '#147a5c',
        'BG': '#121820',
        'BG_ELEVATED': '#24303c',
        'BG_INPUT': '#0e141a',
        'BG_PANEL': '#1a222c',
        'BORDER': '#3d4a57',
        'BORDER_SOFT': '#2c3844',
        'DANGER': '#e07a7a',
        'GRAY_APPLY': '#8b97a3',
        'GRAY_APPLY_BG': '#232b33',
        'GRAY_STRIPE': '#6a7682',
        'INVITE': '#6eb6ff',
        'INVITE_BG': '#16324a',
        'NEW_STRIPE': '#f0f4f8',
        'OK': '#6fd68a',
        'POINTER_BG': '#185a30',
        'POINTER_FG': '#9affb0',
        'POINTER_STRIPE': '#45ff7a',
        'RADIUS': '14',
        'TEXT': '#eef3f7',
        'TEXT_DIM': '#9aabba',
        'TEXT_MUTED': '#6f8191',
        'WARN': '#e6c35c',
        'WHITE_FG': '#ffffff',
        'WHITE_STRIPE': '#ffffff'},
 '02': {'ACCENT': '#34d399',
        'ACCENT_DIM': '#1a7a55',
        'BG': '#121212',
        'BG_ELEVATED': '#222222',
        'BG_INPUT': '#0a0a0a',
        'BG_PANEL': '#181818',
        'BORDER': '#3a3a3a',
        'BORDER_SOFT': '#2a2a2a',
        'DANGER': '#f87171',
        'GRAY_APPLY': '#a1a1aa',
        'GRAY_APPLY_BG': '#27272a',
        'GRAY_STRIPE': '#71717a',
        'INVITE': '#60a5fa',
        'INVITE_BG': '#0f2744',
        'NEW_STRIPE': '#f4f4f5',
        'OK': '#4ade80',
        'POINTER_BG': '#14532d',
        'POINTER_FG': '#86efac',
        'POINTER_STRIPE': '#4ade80',
        'RADIUS': '6',
        'TEXT': '#eaeaea',
        'TEXT_DIM': '#9e9e9e',
        'TEXT_MUTED': '#6e6e6e',
        'WARN': '#facc15',
        'WHITE_FG': '#fafafa',
        'WHITE_STRIPE': '#fafafa'},
 '03': {'ACCENT': '#60a5fa',
        'ACCENT_DIM': '#1d4ed8',
        'BG': '#0f172a',
        'BG_ELEVATED': '#334155',
        'BG_INPUT': '#0b1220',
        'BG_PANEL': '#1e293b',
        'BORDER': '#475569',
        'BORDER_SOFT': '#334155',
        'DANGER': '#f87171',
        'GRAY_APPLY': '#94a3b8',
        'GRAY_APPLY_BG': '#1e293b',
        'GRAY_STRIPE': '#64748b',
        'INVITE': '#a78bfa',
        'INVITE_BG': '#2e1065',
        'NEW_STRIPE': '#f1f5f9',
        'OK': '#4ade80',
        'POINTER_BG': '#166534',
        'POINTER_FG': '#86efac',
        'POINTER_STRIPE': '#4ade80',
        'RADIUS': '10',
        'TEXT': '#e2e8f0',
        'TEXT_DIM': '#94a3b8',
        'TEXT_MUTED': '#64748b',
        'WARN': '#fbbf24',
        'WHITE_FG': '#f8fafc',
        'WHITE_STRIPE': '#f8fafc'},
 '04': {'ACCENT': '#6ec8b8',
        'ACCENT_DIM': '#3d7a70',
        'BG': '#1c2128',
        'BG_ELEVATED': '#2e3640',
        'BG_INPUT': '#181c22',
        'BG_PANEL': '#252b33',
        'BORDER': '#4a5562',
        'BORDER_SOFT': '#3a4450',
        'DANGER': '#d47878',
        'GRAY_APPLY': '#9aa3ad',
        'GRAY_APPLY_BG': '#2a3038',
        'GRAY_STRIPE': '#6b7280',
        'INVITE': '#7eb6f0',
        'INVITE_BG': '#1e3348',
        'NEW_STRIPE': '#dfe6ee',
        'OK': '#7bc47f',
        'POINTER_BG': '#1f5c32',
        'POINTER_FG': '#8dff9a',
        'POINTER_STRIPE': '#3dff6a',
        'RADIUS': '12',
        'TEXT': '#e8edf2',
        'TEXT_DIM': '#a8b3c0',
        'TEXT_MUTED': '#7d8a99',
        'WARN': '#e6c35c',
        'WHITE_FG': '#f5f7fa',
        'WHITE_STRIPE': '#e8edf2'}}


def get_palette(theme_id: str) -> Dict[str, str]:
    tid = str(theme_id or "04")
    if tid not in PALETTES:
        tid = "04"
    return deepcopy(PALETTES[tid])


def build_qss(p: Dict[str, str]) -> str:
    r = p.get("RADIUS", "12")
    # Token replace avoids nested brace hell
    tpl = '''

* {
    font-family: "Segoe UI", "Arial", sans-serif;
    font-size: 16px;
    color: @@TEXT@@;
}
QMainWindow, QWidget {
    background-color: @@BG@@;
    color: @@TEXT@@;
}
QLabel {
    color: @@TEXT@@;
    font-size: 16px;
    background: transparent;
}
QLabel#sectionTitle {
    font-size: 19px;
    font-weight: 700;
    color: @@TEXT@@;
    padding: 6px 0 10px 0;
}
QLabel#hotkeyBadge {
    font-size: 22px;
    font-weight: 700;
    color: @@ACCENT@@;
    padding: 10px 16px;
    background-color: @@BG_ELEVATED@@;
    border: 2px solid @@ACCENT_DIM@@;
    border-radius: @@RADIUS@@px;
}
QLabel#statsValue {
    font-size: 20px;
    font-weight: 700;
    color: @@ACCENT@@;
}
QLabel#mutedLabel {
    font-size: 15px;
    color: @@TEXT_MUTED@@;
}
QLabel#legendChip {
    font-size: 15px;
    font-weight: 700;
    padding: 8px 14px;
    border-radius: 8px;
    border: 2px solid @@BORDER@@;
}
QGroupBox {
    font-size: 17px;
    font-weight: 700;
    color: @@TEXT@@;
    border: 1px solid @@BORDER@@;
    border-radius: @@RADIUS@@px;
    margin-top: 16px;
    padding-top: 20px;
    padding-left: 14px;
    padding-right: 14px;
    padding-bottom: 12px;
    background-color: @@BG_PANEL@@;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 8px;
    color: @@ACCENT@@;
}
QScrollArea {
    background-color: @@BG@@;
    border: none;
}
QScrollArea > QWidget > QWidget {
    background-color: @@BG@@;
}
QListWidget {
    background-color: @@BG_INPUT@@;
    border: 1px solid @@BORDER@@;
    border-radius: @@RADIUS@@px;
    padding: 8px;
    font-size: 18px;
    outline: none;
}
QListWidget::item {
    padding: 14px 12px 14px 14px;
    margin: 4px 2px;
    border-radius: 10px;
    border: 1px solid transparent;
    min-height: 52px;
}
QListWidget::item:selected {
    border: 2px solid @@ACCENT@@;
}
QListWidget::item:hover:!selected {
    border: 1px solid @@BORDER@@;
}
QTextEdit {
    background-color: @@BG_INPUT@@;
    border: 1px solid @@BORDER@@;
    border-radius: @@RADIUS@@px;
    padding: 12px;
    font-size: 17px;
    selection-background-color: @@ACCENT_DIM@@;
}
QCheckBox {
    font-size: 17px;
    spacing: 12px;
    padding: 8px 2px;
    color: @@TEXT@@;
    background: transparent;
}
QCheckBox::indicator {
    width: 24px;
    height: 24px;
    border-radius: 7px;
    border: 2px solid @@BORDER@@;
    background: @@BG_INPUT@@;
}
QCheckBox::indicator:checked {
    background-color: @@ACCENT@@;
    border-color: @@ACCENT@@;
}
QComboBox {
    background-color: @@BG_ELEVATED@@;
    color: @@TEXT@@;
    border: 1px solid @@BORDER@@;
    border-radius: 10px;
    padding: 10px 12px;
    font-size: 16px;
    min-height: 28px;
}
QComboBox QAbstractItemView {
    background-color: @@BG_PANEL@@;
    color: @@TEXT@@;
    selection-background-color: @@ACCENT_DIM@@;
}
QPushButton {
    background-color: @@BG_ELEVATED@@;
    color: @@TEXT@@;
    border: 1px solid @@BORDER@@;
    border-radius: @@RADIUS@@px;
    padding: 12px 18px;
    font-size: 16px;
    font-weight: 600;
    min-height: 26px;
}
QPushButton:hover {
    border: 2px solid @@ACCENT@@;
}
QPushButton:disabled {
    color: @@TEXT_MUTED@@;
    border-color: @@BORDER_SOFT@@;
}
QPushButton#primaryBtn {
    background-color: @@ACCENT_DIM@@;
    border: 2px solid @@ACCENT@@;
    color: #f2fffc;
}
QPushButton#okBtn {
    background-color: #2d4a32;
    border: 2px solid @@OK@@;
}
QPushButton#dangerBtn {
    background-color: #4a2e2e;
    border: 2px solid @@DANGER@@;
}
QPushButton#warnBtn {
    background-color: #4a4020;
    border: 2px solid @@WARN@@;
}
QPushButton#ghostBtn {
    background-color: transparent;
    border: 1px dashed @@BORDER@@;
}
QStatusBar {
    background-color: @@BG_PANEL@@;
    color: @@TEXT_DIM@@;
    font-size: 15px;
    border-top: 1px solid @@BORDER_SOFT@@;
    padding: 6px 12px;
}
QSplitter::handle {
    background-color: @@BORDER_SOFT@@;
    width: 4px;
    margin: 8px 4px;
    border-radius: 2px;
}
QScrollBar:vertical {
    background: @@BG@@;
    width: 16px;
    margin: 2px;
    border: none;
}
QScrollBar::handle:vertical {
    background: @@BORDER@@;
    min-height: 40px;
    border-radius: 8px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QMessageBox {
    background-color: @@BG_PANEL@@;
}
QMessageBox QLabel {
    font-size: 17px;
    color: @@TEXT@@;
    min-width: 420px;
}
QToolButton#navBtn {
    background: transparent;
    border: none;
    border-bottom: 3px solid transparent;
    color: @@TEXT_DIM@@;
    padding: 6px 10px;
    font-size: 13px;
    font-weight: 600;
}
QToolButton#navBtn:checked {
    color: @@ACCENT@@;
    border-bottom: 3px solid @@ACCENT@@;
}
QToolButton#navBtn:hover {
    color: @@TEXT@@;
}
QLabel#detailTitle {
    font-size: 26px;
    font-weight: 700;
    color: @@ACCENT@@;
}
QLabel#detailCompany {
    font-size: 15px;
    color: @@TEXT_DIM@@;
}
QLabel#detailScore {
    font-size: 28px;
    font-weight: 700;
    color: @@ACCENT@@;
}
QFrame#panelCard {
    background-color: @@BG_PANEL@@;
    border: 1px solid @@BORDER_SOFT@@;
    border-radius: 12px;
    padding: 8px;
}
QFrame#statsStrip {
    background-color: @@BG_PANEL@@;
    border: 1px solid @@BORDER_SOFT@@;
    border-radius: 12px;
}
QListWidget#vacancyList {
    background-color: @@BG@@;
    border: none;
    padding: 2px;
}
QListWidget#vacancyList::item {
    border: none;
    background: transparent;
    padding: 0;
    margin: 0;
}

'''
    out = tpl
    for k, v in p.items():
        out = out.replace("@@" + k + "@@", str(v))
    return out
