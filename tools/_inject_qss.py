# -*- coding: utf-8 -*-
from pathlib import Path

p = Path(__file__).resolve().parent.parent / "radar" / "themes.py"
t = p.read_text(encoding="utf-8")
if "QToolButton#navBtn" in t:
    print("already")
else:
    extra = """
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
"""
    close = t.find("'''", t.find("tpl ="))
    assert close > 0
    t = t[:close] + extra + t[close:]
    p.write_text(t, encoding="utf-8")
    print("injected at", close)

from radar.themes import build_qss, get_palette

q = build_qss(get_palette("04"))
assert "navBtn" in q and "detailTitle" in q
print("qss ok", len(q))
