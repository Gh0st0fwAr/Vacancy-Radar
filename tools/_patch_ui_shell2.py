# -*- coding: utf-8 -*-
"""Patch ui.py to use reference-04 shell. ASCII-only source."""
from pathlib import Path

path = Path(__file__).resolve().parent.parent / "radar" / "ui.py"
text = path.read_text(encoding="utf-8")

start = text.find("from radar.autostart import")
end = text.find("\ndef log(")
if start < 0 or end < 0:
    raise SystemExit("markers fail %s %s" % (start, end))

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
if b0 < 0 or b1 < 0:
    raise SystemExit("build markers")
text = (
    text[:b0]
    + "    def _build_ui(self):\n"
    + "        attach_shell(self)\n"
    + "\n"
    + "    def show_page(self, index: int):\n"
    + "        self.pages.setCurrentIndex(index)\n"
    + "        for i, btn in enumerate((self.nav_queue, self.nav_stats, self.nav_settings)):\n"
    + "            btn.setChecked(i == index)\n"
    + "\n"
    + text[b1:]
)

r0 = text.find("    def refresh_queue_list(self):")
r1 = text.find("    def on_select(self, row: int):")
if r0 < 0 or r1 < 0:
    raise SystemExit("refresh markers")

arrow = "\u2192 "
dot = " \u00b7 "
vac_word = "\u0412\u0430\u043a\u0430\u043d\u0441\u0438\u0438"

refresh = f'''    def refresh_queue_list(self):
        prev = self.selected_url()
        self.list.clear()
        new_count = 0
        visible = 0
        applied_n = 0
        active = self.store.active_url or self._opening_url or ""
        for v in self.store.items:
            if v.status == "banned":
                continue
            visible += 1
            is_active = bool(active and v.url == active)
            kind = status_kind(v, is_active=is_active)
            if kind == "new":
                new_count += 1
            if kind == "apply":
                applied_n += 1
            item = QListWidgetItem()
            item.setData(Qt.UserRole, v.url)
            item.setData(ACTIVE_ROLE, is_active)
            item.setData(HH_HIGHLIGHT_ROLE, is_blue(v))
            item.setData(STATUS_KIND_ROLE, kind)
            title = v.title or ""
            if is_active and not title.startswith("{arrow}"):
                title = "{arrow}" + title
            item.setData(TITLE_ROLE, title)
            item.setData(COMPANY_ROLE, v.company or "")
            meta_bits = []
            if v.remote:
                meta_bits.append("Remote")
            if v.salary:
                meta_bits.append(v.salary)
            if v.published:
                meta_bits.append(str(v.published))
            elif v.found_at:
                meta_bits.append(str(v.found_at)[:16].replace("T", " "))
            item.setData(META_ROLE, "{dot}".join(meta_bits))
            item.setData(SCORE_ROLE, int(v.score or 0))
            item.setData(PILL_ROLE, pill_label(kind, v))
            item.setData(Qt.DisplayRole, title)
            ic = icon_for(v)
            if not ic.isNull():
                item.setIcon(ic)
            self.list.addItem(item)
        self.lbl_queue.setText(str(new_count))
        if hasattr(self, "lbl_vac_count"):
            self.lbl_vac_count.setText(f"{vac_word} ({{visible}})")
        if hasattr(self, "lbl_strip_new"):
            self.lbl_strip_new.setText(str(new_count))
            self.lbl_strip_total.setText(str(visible))
            self.lbl_strip_applied.setText(str(applied_n))
        restore = active or prev
        if restore:
            self._select_url(restore)

'''
text = text[:r0] + refresh + text[r1:]

o0 = text.find("    def on_select(self, row: int):")
o1 = text.find("    def copy_selected_letter(self):")
if o0 < 0 or o1 < 0:
    raise SystemExit("on_select markers")

zp = "\u0417\u041f"
st = "\u0421\u0442\u0430\u0442\u0443\u0441"
pis = "\u041f\u0438\u0441\u044c\u043c\u043e"
pochemu = "\u041f\u043e\u0447\u0435\u043c\u0443 (\u0442\u043e\u043b\u044c\u043a\u043e \u0434\u043b\u044f \u0442\u0435\u0431\u044f)"
neuk = "\u043d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d\u0430"
em = "\u2014"
nl = "\n"

on_select = f'''    def on_select(self, row: int):
        if row < 0:
            return
        item = self.list.item(row)
        url = item.data(Qt.UserRole)
        v = next((x for x in self.store.items if x.url == url), None)
        if not v:
            return
        if hasattr(self, "lbl_detail_title"):
            self.lbl_detail_title.setText(v.title or "")
            self.lbl_detail_company.setText(v.company or "")
            meta = []
            if v.remote:
                meta.append("Remote")
            if v.salary:
                meta.append(v.salary)
            if v.published:
                meta.append(str(v.published))
            self.lbl_detail_meta.setText("{dot}".join(meta) if meta else "")
            sc = int(v.score or 0)
            self.lbl_detail_score.setText(f"{{sc}} / 100" if sc else "{em}")
        salary = v.salary or "{neuk}"
        letter_src = v.letter_source or "{em}"
        reasons = {nl!r}.join(v.reasons)
        self.detail.setPlainText(
            f"{{v.title}}{nl}{{v.company}}{nl}{{v.url}}{nl}{nl}"
            f"Score: {{v.score}}%{nl}{zp}: {{salary}}{nl}{st}: {{v.status}}{nl}"
            f"{pis}: {{letter_src}}{nl}{nl}"
            f"{pochemu}:{nl}{{reasons}}"
        )
        self.letter_view.setPlainText(v.cover_letter or "")

'''
text = text[:o0] + on_select + text[o1:]

s1 = text.find("    def capture_hotkey(self):")
if "lbl_strip_replies" not in text[text.find("def refresh_stats_labels"):s1]:
    insert = '''
        if hasattr(self, "lbl_strip_replies"):
            self.lbl_strip_replies.setText(fmt(st.get("invitations")))
            self.lbl_strip_interviews.setText(fmt(st.get("interviews")))
            self.lbl_strip_offers.setText(fmt(st.get("unread_messages")))
            self.lbl_strip_updated.setText("Updated: " + (st.get("updated_at") or "—"))
            if st.get("total_responses") is not None:
                self.lbl_strip_total.setText(fmt(st.get("total_responses")))

'''
    text = text[:s1] + insert + text[s1:]

# Drop unused imports that may cause lint issues later - keep QComboBox etc if unused ok

path.write_text(text, encoding="utf-8")
src = path.read_text(encoding="utf-8")
compile(src, str(path), "exec")
print("ui patched", path.stat().st_size)
