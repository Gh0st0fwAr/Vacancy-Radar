# -*- coding: utf-8 -*-
from pathlib import Path

path = Path(__file__).resolve().parent.parent / "radar" / "ui.py"
text = path.read_text(encoding="utf-8")

start = text.find("from radar.autostart import")
end = text.find("\ndef log(")
assert start >= 0 and end >= 0

new_mid = """from radar.autostart import is_autostart_enabled, set_autostart
from radar.queue_style import (
    ICON_SIZE,
    STATUS_KIND_ROLE,
    colors_for_kind,
    icon_for,
    is_blue,
    pill_label,
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
from radar.ui_shell import attach_shell
from radar.vacancy_delegate import (
    ACTIVE_ROLE,
    COMPANY_ROLE,
    META_ROLE,
    PILL_ROLE,
    SCORE_ROLE,
    TITLE_ROLE,
)

HH_HIGHLIGHT_ROLE = Qt.UserRole + 2


"""
text = text[:start] + new_mid + text[end + 1 :]

d0 = text.find("\nclass StatusListDelegate")
d1 = text.find("\ndef log(")
if d0 > 0 and d1 > d0:
    text = text[:d0] + "\n" + text[d1:]

b0 = text.find("    def _build_ui(self):")
b1 = text.find("    def _build_tray(self):")
assert b0 >= 0 and b1 >= 0
text = (
    text[:b0]
    + "    def _build_ui(self):\n"
    + "        attach_shell(self)\n\n"
    + "    def show_page(self, index: int):\n"
    + "        self.pages.setCurrentIndex(index)\n"
    + "        for i, btn in enumerate((self.nav_queue, self.nav_stats, self.nav_settings)):\n"
    + "            btn.setChecked(i == index)\n\n"
    + text[b1:]
)

arrow = chr(0x2192) + " "
dot = " " + chr(0x00B7) + " "
vac = "".join(chr(c) for c in (0x0412, 0x0430, 0x043A, 0x0430, 0x043D, 0x0441, 0x0438, 0x0438))
em = chr(0x2014)
nl = "\n"
zp = "".join(chr(c) for c in (0x0417, 0x041F))
st = "".join(chr(c) for c in (0x0421, 0x0442, 0x0430, 0x0442, 0x0443, 0x0441))
pis = "".join(chr(c) for c in (0x041F, 0x0438, 0x0441, 0x044C, 0x043C, 0x043E))
pochemu = "".join(
    chr(c)
    for c in (
        0x041F,
        0x043E,
        0x0447,
        0x0435,
        0x043C,
        0x0443,
        0x20,
        0x28,
        0x0442,
        0x043E,
        0x043B,
        0x044C,
        0x043A,
        0x043E,
        0x20,
        0x0434,
        0x043B,
        0x044F,
        0x20,
        0x0442,
        0x0435,
        0x0431,
        0x044F,
        0x29,
    )
)
neuk = "".join(
    chr(c)
    for c in (0x043D, 0x0435, 0x20, 0x0443, 0x043A, 0x0430, 0x0437, 0x0430, 0x043D, 0x0430)
)

r0 = text.find("    def refresh_queue_list(self):")
r1 = text.find("    def on_select(self, row: int):")
assert r0 >= 0 and r1 >= 0

refresh = (
    "    def refresh_queue_list(self):\n"
    "        prev = self.selected_url()\n"
    "        self.list.clear()\n"
    "        new_count = 0\n"
    "        visible = 0\n"
    "        applied_n = 0\n"
    '        active = self.store.active_url or self._opening_url or ""\n'
    "        for v in self.store.items:\n"
    '            if v.status == "banned":\n'
    "                continue\n"
    "            visible += 1\n"
    "            is_active = bool(active and v.url == active)\n"
    "            kind = status_kind(v, is_active=is_active)\n"
    '            if kind == "new":\n'
    "                new_count += 1\n"
    '            if kind == "apply":\n'
    "                applied_n += 1\n"
    "            item = QListWidgetItem()\n"
    "            item.setData(Qt.UserRole, v.url)\n"
    "            item.setData(ACTIVE_ROLE, is_active)\n"
    "            item.setData(HH_HIGHLIGHT_ROLE, is_blue(v))\n"
    "            item.setData(STATUS_KIND_ROLE, kind)\n"
    '            title = v.title or ""\n'
    "            if is_active and not title.startswith(" + repr(arrow) + "):\n"
    "                title = " + repr(arrow) + " + title\n"
    "            item.setData(TITLE_ROLE, title)\n"
    '            item.setData(COMPANY_ROLE, v.company or "")\n'
    "            meta_bits = []\n"
    "            if v.remote:\n"
    '                meta_bits.append("Remote")\n'
    "            if v.salary:\n"
    "                meta_bits.append(v.salary)\n"
    "            if v.published:\n"
    "                meta_bits.append(str(v.published))\n"
    "            elif v.found_at:\n"
    '                meta_bits.append(str(v.found_at)[:16].replace("T", " "))\n'
    "            item.setData(META_ROLE, " + repr(dot) + ".join(meta_bits))\n"
    "            item.setData(SCORE_ROLE, int(v.score or 0))\n"
    "            item.setData(PILL_ROLE, pill_label(kind, v))\n"
    "            item.setData(Qt.DisplayRole, title)\n"
    "            ic = icon_for(v)\n"
    "            if not ic.isNull():\n"
    "                item.setIcon(ic)\n"
    "            self.list.addItem(item)\n"
    "        self.lbl_queue.setText(str(new_count))\n"
    '        if hasattr(self, "lbl_vac_count"):\n'
    "            self.lbl_vac_count.setText(" + repr(vac + " (%d)") + " % visible)\n"
    '        if hasattr(self, "lbl_strip_new"):\n'
    "            self.lbl_strip_new.setText(str(new_count))\n"
    "            self.lbl_strip_total.setText(str(visible))\n"
    "            self.lbl_strip_applied.setText(str(applied_n))\n"
    "        restore = active or prev\n"
    "        if restore:\n"
    "            self._select_url(restore)\n\n"
)
text = text[:r0] + refresh + text[r1:]

o0 = text.find("    def on_select(self, row: int):")
o1 = text.find("    def copy_selected_letter(self):")
assert o0 >= 0 and o1 >= 0

on_select = (
    "    def on_select(self, row: int):\n"
    "        if row < 0:\n"
    "            return\n"
    "        item = self.list.item(row)\n"
    "        url = item.data(Qt.UserRole)\n"
    "        v = next((x for x in self.store.items if x.url == url), None)\n"
    "        if not v:\n"
    "            return\n"
    '        if hasattr(self, "lbl_detail_title"):\n'
    '            self.lbl_detail_title.setText(v.title or "")\n'
    '            self.lbl_detail_company.setText(v.company or "")\n'
    "            meta = []\n"
    "            if v.remote:\n"
    '                meta.append("Remote")\n'
    "            if v.salary:\n"
    "                meta.append(v.salary)\n"
    "            if v.published:\n"
    "                meta.append(str(v.published))\n"
    "            self.lbl_detail_meta.setText((" + repr(dot) + ".join(meta)) if meta else '')\n"
    "            sc = int(v.score or 0)\n"
    "            self.lbl_detail_score.setText(('%d / 100' % sc) if sc else " + repr(em) + ")\n"
    "        salary = v.salary or " + repr(neuk) + "\n"
    "        letter_src = v.letter_source or " + repr(em) + "\n"
    "        reasons = " + repr(nl) + ".join(v.reasons)\n"
    "        parts = [v.title, v.company, v.url, '',\n"
    "                 'Score: %s%%' % v.score,\n"
    "                 '%s: %s' % (" + repr(zp) + ", salary),\n"
    "                 '%s: %s' % (" + repr(st) + ", v.status),\n"
    "                 '%s: %s' % (" + repr(pis) + ", letter_src),\n"
    "                 '',\n"
    "                 '%s:' % (" + repr(pochemu) + "),\n"
    "                 reasons]\n"
    "        self.detail.setPlainText(" + repr(nl) + ".join(parts))\n"
    "        self.letter_view.setPlainText(v.cover_letter or '')\n\n"
)
text = text[:o0] + on_select + text[o1:]

s1 = text.find("    def capture_hotkey(self):")
rs = text.find("def refresh_stats_labels")
if "lbl_strip_replies" not in text[rs:s1]:
    insert = (
        "\n"
        '        if hasattr(self, "lbl_strip_replies"):\n'
        '            self.lbl_strip_replies.setText(fmt(st.get("invitations")))\n'
        '            self.lbl_strip_interviews.setText(fmt(st.get("interviews")))\n'
        '            self.lbl_strip_offers.setText(fmt(st.get("unread_messages")))\n'
        '            self.lbl_strip_updated.setText("Updated: " + (st.get("updated_at") or '
        + repr(em)
        + "))\n"
        '            if st.get("total_responses") is not None:\n'
        '                self.lbl_strip_total.setText(fmt(st.get("total_responses")))\n'
        "\n"
    )
    text = text[:s1] + insert + text[s1:]

path.write_text(text, encoding="utf-8")
compile(path.read_text(encoding="utf-8"), str(path), "exec")
print("OK", path.stat().st_size)
