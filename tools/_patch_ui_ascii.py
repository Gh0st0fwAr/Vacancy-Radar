# -*- coding: utf-8 -*-
from pathlib import Path

path = Path(__file__).resolve().parent.parent / "radar" / "ui.py"
text = path.read_text(encoding="utf-8")

start = text.find("from radar.autostart import")
end = text.find("\ndef log(")
if start < 0 or end < 0:
    raise SystemExit("markers fail")

new_mid = (
    "from radar.autostart import is_autostart_enabled, set_autostart\n"
    "from radar.queue_style import (\n"
    "    ICON_SIZE,\n"
    "    STATUS_KIND_ROLE,\n"
    "    colors_for_kind,\n"
    "    icon_for,\n"
    "    is_blue,\n"
    "    pill_label,\n"
    "    status_kind,\n"
    ")\n"
    "from radar.stats_hh import fetch_stats\n"
    "from radar import theme as theme_mod\n"
    "from radar.theme import (\n"
    "    ScaleButton,\n"
    "    THEME_LABELS,\n"
    "    apply_app_font,\n"
    "    apply_theme,\n"
    ")\n"
    "from radar.themes import THEME_IDS\n"
    "from radar.ui_shell import attach_shell\n"
    "from radar.vacancy_delegate import (\n"
    "    ACTIVE_ROLE,\n"
    "    COMPANY_ROLE,\n"
    "    META_ROLE,\n"
    "    PILL_ROLE,\n"
    "    SCORE_ROLE,\n"
    "    TITLE_ROLE,\n"
    ")\n"
    "\n"
    "HH_HIGHLIGHT_ROLE = Qt.UserRole + 2\n"
    "\n"
    "\n"
)
text = text[:start] + new_mid + text[end + 1 :]

d0 = text.find("\nclass StatusListDelegate")
d1 = text.find("\ndef log(")
if d0 > 0 and d1 > d0:
    text = text[:d0] + "\n" + text[d1:]

b0 = text.find("    def _build_ui(self):")
b1 = text.find("    def _build_tray(self):")
if b0 < 0 or b1 < 0:
    raise SystemExit("build markers")

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
vac = (
    chr(0x0412)
    + chr(0x0430)
    + chr(0x043A)
    + chr(0x0430)
    + chr(0x043D)
    + chr(0x0441)
    + chr(0x0438)
    + chr(0x0438)
)
em = chr(0x2014)
nl = "\n"
zp = chr(0x0417) + chr(0x041F)
st = chr(0x0421) + chr(0x0442) + chr(0x0430) + chr(0x0442) + chr(0x0443) + chr(0x0441)
pis = chr(0x041F) + chr(0x0438) + chr(0x0441) + chr(0x044C) + chr(0x043C) + chr(0x043E)
pochemu = (
    chr(0x041F)
    + chr(0x043E)
    + chr(0x0447)
    + chr(0x0435)
    + chr(0x043C)
    + chr(0x0443)
    + " ("
    + chr(0x0442)
    + chr(0x043E)
    + chr(0x043B)
    + chr(0x044C)
    + chr(0x043A)
    + chr(0x043E)
    + " "
    + chr(0x0434)
    + chr(0x043B)
    + chr(0x044F)
    + " "
    + chr(0x0442)
    + chr(0x0435)
    + chr(0x0431)
    + chr(0x044F)
    + ")"
)
neuk = (
    chr(0x043D)
    + chr(0x0435)
    + " "
    + chr(0x0443)
    + chr(0x043A)
    + chr(0x0430)
    + chr(0x0437)
    + chr(0x0430)
    + chr(0x043D)
    + chr(0x0430)
)

r0 = text.find("    def refresh_queue_list(self):")
r1 = text.find("    def on_select(self, row: int):")
if r0 < 0 or r1 < 0:
    raise SystemExit("refresh markers")

refresh_lines = [
    "    def refresh_queue_list(self):",
    "        prev = self.selected_url()",
    "        self.list.clear()",
    "        new_count = 0",
    "        visible = 0",
    "        applied_n = 0",
    '        active = self.store.active_url or self._opening_url or ""',
    "        for v in self.store.items:",
    '            if v.status == "banned":',
    "                continue",
    "            visible += 1",
    "            is_active = bool(active and v.url == active)",
    "            kind = status_kind(v, is_active=is_active)",
    '            if kind == "new":',
    "                new_count += 1",
    '            if kind == "apply":',
    "                applied_n += 1",
    "            item = QListWidgetItem()",
    "            item.setData(Qt.UserRole, v.url)",
    "            item.setData(ACTIVE_ROLE, is_active)",
    "            item.setData(HH_HIGHLIGHT_ROLE, is_blue(v))",
    "            item.setData(STATUS_KIND_ROLE, kind)",
    '            title = v.title or ""',
    "            if is_active and not title.startswith(%r):" % arrow,
    "                title = %r + title" % arrow,
    "            item.setData(TITLE_ROLE, title)",
    '            item.setData(COMPANY_ROLE, v.company or "")',
    "            meta_bits = []",
    "            if v.remote:",
    '                meta_bits.append("Remote")',
    "            if v.salary:",
    "                meta_bits.append(v.salary)",
    "            if v.published:",
    "                meta_bits.append(str(v.published))",
    "            elif v.found_at:",
    '                meta_bits.append(str(v.found_at)[:16].replace("T", " "))',
    "            item.setData(META_ROLE, %r.join(meta_bits))" % dot,
    "            item.setData(SCORE_ROLE, int(v.score or 0))",
    "            item.setData(PILL_ROLE, pill_label(kind, v))",
    "            item.setData(Qt.DisplayRole, title)",
    "            ic = icon_for(v)",
    "            if not ic.isNull():",
    "                item.setIcon(ic)",
    "            self.list.addItem(item)",
    "        self.lbl_queue.setText(str(new_count))",
    '        if hasattr(self, "lbl_vac_count"):',
    "            self.lbl_vac_count.setText(%r + f\" ({{visible}})\")" % vac,
    '        if hasattr(self, "lbl_strip_new"):',
    "            self.lbl_strip_new.setText(str(new_count))",
    "            self.lbl_strip_total.setText(str(visible))",
    "            self.lbl_strip_applied.setText(str(applied_n))",
    "        restore = active or prev",
    "        if restore:",
    "            self._select_url(restore)",
    "",
]
# fix the vac line - the f-string braces got doubled wrong
refresh_lines[-8] = (
    '            self.lbl_vac_count.setText("%s (%s)" % (%r, visible))' % vac
)
# Actually simpler:
refresh_lines = [ln for ln in refresh_lines if "lbl_vac_count.setText" not in ln or True]
# rebuild vac line cleanly
out = []
for ln in refresh_lines:
    if "lbl_vac_count.setText" in ln:
        out.append(
            "            self.lbl_vac_count.setText(%r %% visible)"
            % (vac + " (%d)")
        )
    else:
        out.append(ln)
refresh = "\n".join(out) + "\n"

text = text[:r0] + refresh + text[r1:]

o0 = text.find("    def on_select(self, row: int):")
o1 = text.find("    def copy_selected_letter(self):")
if o0 < 0 or o1 < 0:
    raise SystemExit("on_select markers")

on_lines = [
    "    def on_select(self, row: int):",
    "        if row < 0:",
    "            return",
    "        item = self.list.item(row)",
    "        url = item.data(Qt.UserRole)",
    "        v = next((x for x in self.store.items if x.url == url), None)",
    "        if not v:",
    "            return",
    '        if hasattr(self, "lbl_detail_title"):',
    '            self.lbl_detail_title.setText(v.title or "")',
    '            self.lbl_detail_company.setText(v.company or "")',
    "            meta = []",
    "            if v.remote:",
    '                meta.append("Remote")',
    "            if v.salary:",
    "                meta.append(v.salary)",
    "            if v.published:",
    "                meta.append(str(v.published))",
    "            self.lbl_detail_meta.setText(%r.join(meta) if meta else %r)"
    % (dot, ""),
    "            sc = int(v.score or 0)",
    '            self.lbl_detail_score.setText(("%d / 100" % sc) if sc else %r)'
    % em,
    "        salary = v.salary or %r" % neuk,
    "        letter_src = v.letter_source or %r" % em,
    "        reasons = %r.join(v.reasons)" % nl,
    "        self.detail.setPlainText(",
    "            %r" % (("%s" + nl + "%s" + nl + "%s" + nl + nl),)
    + " % (v.title, v.company, v.url)",
]
# This is getting too fragile. Write on_select as a single exec template.

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
marker = "lbl_strip_replies"
block = text[text.find("def refresh_stats_labels") : s1]
if marker not in block:
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
