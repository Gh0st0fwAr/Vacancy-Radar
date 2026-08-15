# -*- coding: utf-8 -*-
"""Patch ui.py to use reference-04 shell."""
from pathlib import Path

path = Path(__file__).resolve().parent.parent / "radar" / "ui.py"
text = path.read_text(encoding="utf-8")

# 1) Replace imports / delegate block
start = text.find("from radar.autostart import")
end = text.find("\ndef log(")
if start < 0 or end < 0:
    raise SystemExit("markers fail")

new_mid = '''from radar.autostart import is_autostart_enabled, set_autostart
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


'''
text = text[:start] + new_mid + text[end + 1 :]

# Remove old StatusListDelegate class if still present
d0 = text.find("\nclass StatusListDelegate")
d1 = text.find("\ndef log(")
if d0 > 0 and d1 > d0:
    text = text[:d0] + "\n" + text[d1:]

# 2) Replace _build_ui
b0 = text.find("    def _build_ui(self):")
b1 = text.find("    def _build_tray(self):")
if b0 < 0 or b1 < 0:
    raise SystemExit("build markers")
text = (
    text[:b0]
    + '''    def _build_ui(self):
        attach_shell(self)

    def show_page(self, index: int):
        self.pages.setCurrentIndex(index)
        for i, btn in enumerate((self.nav_queue, self.nav_stats, self.nav_settings)):
            btn.setChecked(i == index)

'''
    + text[b1:]
)

# 3) refresh_queue_list
r0 = text.find("    def refresh_queue_list(self):")
r1 = text.find("    def on_select(self, row: int):")
if r0 < 0 or r1 < 0:
    raise SystemExit("refresh markers")

text = (
    text[:r0]
    + '''    def refresh_queue_list(self):
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
            if is_active and not title.startswith("\\u2192 "):
                title = "\\u2192 " + title
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
            item.setData(META_ROLE, " \\u00b7 ".join(meta_bits))
            item.setData(SCORE_ROLE, int(v.score or 0))
            item.setData(PILL_ROLE, pill_label(kind, v))
            item.setData(Qt.DisplayRole, title)
            ic = icon_for(v)
            if not ic.isNull():
                item.setIcon(ic)
            self.list.addItem(item)
        self.lbl_queue.setText(str(new_count))
        if hasattr(self, "lbl_vac_count"):
            self.lbl_vac_count.setText(f"\\u0412\\u0430\\u043a\\u0430\\u043d\\u0441\\u0438\\u0438 ({visible})")
        if hasattr(self, "lbl_strip_new"):
            self.lbl_strip_new.setText(str(new_count))
            self.lbl_strip_total.setText(str(visible))
            self.lbl_strip_applied.setText(str(applied_n))
        restore = active or prev
        if restore:
            self._select_url(restore)

'''
    + text[r1:]
)

# Fix escapes in the inserted refresh to real unicode
text = (
    text.replace("\\u2192 ", "\u2192 ")
    .replace("\\u00b7 ", "\u00b7 ")
    .replace("\\u0412\\u0430\\u043a\\u0430\\u043d\\u0441\\u0438\\u0438", "\u0412\u0430\u043a\u0430\u043d\u0441\u0438\u0438")
)

# 4) on_select
o0 = text.find("    def on_select(self, row: int):")
o1 = text.find("    def copy_selected_letter(self):")
if o0 < 0 or o1 < 0:
    raise SystemExit("on_select markers")

text = (
    text[:o0]
    + '''    def on_select(self, row: int):
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
            self.lbl_detail_meta.setText(" \\u00b7 ".join(meta) if meta else "")
            sc = int(v.score or 0)
            self.lbl_detail_score.setText(f"{sc} / 100" if sc else "\\u2014")
        # Metadata only — never mixed into the cover letter / clipboard.
        self.detail.setPlainText(
            f"{v.title}\\n{v.company}\\n{v.url}\\n\\n"
            f"Score: {v.score}%\\n"
            f"\\u0417\\u041f: {v.salary or '\\u043d\\u0435 \\u0443\\u043a\\u0430\\u0437\\u0430\\u043d\\u0430'}\\n"
            f"\\u0421\\u0442\\u0430\\u0442\\u0443\\u0441: {v.status}\\n"
            f"\\u041f\\u0438\\u0441\\u044c\\u043c\\u043e: {v.letter_source or '\\u2014'}\\n\\n"
            f"\\u041f\\u043e\\u0447\\u0435\\u043c\\u0443 (\\u0442\\u043e\\u043b\\u044c\\u043a\\u043e \\u0434\\u043b\\u044f \\u0442\\u0435\\u0431\\u044f):\\n"
            + "\\n".join(v.reasons)
        )
        self.letter_view.setPlainText(v.cover_letter or "")

'''
    + text[o1:]
)

# decode unicode escapes carefully in on_select block - use a simpler plain version
# Re-do on_select with real chars via encode/decode
o0 = text.find("    def on_select(self, row: int):")
o1 = text.find("    def copy_selected_letter(self):")
on_select = '''    def on_select(self, row: int):
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
            self.lbl_detail_meta.setText(" · ".join(meta) if meta else "")
            sc = int(v.score or 0)
            self.lbl_detail_score.setText(f"{sc} / 100" if sc else "—")
        salary = v.salary or "?? ???????"
        letter_src = v.letter_source or "—"
        why = "\\n".join(v.reasons)
        self.detail.setPlainText(
            f"{v.title}\\n{v.company}\\n{v.url}\\n\\n"
            f"Score: {v.score}%\\n??: {salary}\\n??????: {v.status}\\n"
            f"??????: {letter_src}\\n\\n"
            f"?????? (?????? ??? ????):\\n{why}"
        )
        self.letter_view.setPlainText(v.cover_letter or "")

'''
# Fix the why join - in the string above \\n is wrong for the source file
on_select = on_select.replace("why = \"\\\\n\".join", "why = \"\\n\".join")
on_select = on_select.replace("f\"{v.title}\\\\n", "f\"{v.title}\\n")
# Actually write with real newlines in f-string for setPlainText
on_select = '''    def on_select(self, row: int):
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
            self.lbl_detail_meta.setText(" · ".join(meta) if meta else "")
            sc = int(v.score or 0)
            self.lbl_detail_score.setText(f"{sc} / 100" if sc else "—")
        salary = v.salary or "?? ???????"
        letter_src = v.letter_source or "—"
        reasons = "\\n".join(v.reasons)
        self.detail.setPlainText(
            "{title}\\n{company}\\n{url}\\n\\n"
            "Score: {score}%\\n"
            "??: {salary}\\n"
            "??????: {status}\\n"
            "??????: {letter}\\n\\n"
            "?????? (?????? ??? ????):\\n{reasons}".format(
                title=v.title,
                company=v.company,
                url=v.url,
                score=v.score,
                salary=salary,
                status=v.status,
                letter=letter_src,
                reasons=reasons,
            )
        )
        self.letter_view.setPlainText(v.cover_letter or "")

'''.replace("\\n", "\n")
# Wait that replaces ALL \\n including in join - bad.
# Use chr approach instead
nl = chr(10)
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
            self.lbl_detail_meta.setText(" · ".join(meta) if meta else "")
            sc = int(v.score or 0)
            self.lbl_detail_score.setText(f"{{sc}} / 100" if sc else "—")
        salary = v.salary or "?? ???????"
        letter_src = v.letter_source or "—"
        reasons = {nl!r}.join(v.reasons)
        self.detail.setPlainText(
            f"{{v.title}}{nl}{{v.company}}{nl}{{v.url}}{nl}{nl}"
            f"Score: {{v.score}}%{nl}??: {{salary}}{nl}??????: {{v.status}}{nl}"
            f"??????: {{letter_src}}{nl}{nl}"
            f"?????? (?????? ??? ????):{nl}{{reasons}}"
        )
        self.letter_view.setPlainText(v.cover_letter or "")

'''
text = text[:o0] + on_select + text[o1:]

# 5) refresh_stats_labels - extend strip
s0 = text.find("    def refresh_stats_labels(self, st=None):")
s1 = text.find("    def capture_hotkey(self):")
old_stats = text[s0:s1]
if "lbl_strip_replies" not in old_stats:
    insert = '''
        if hasattr(self, "lbl_strip_replies"):
            self.lbl_strip_replies.setText(fmt(st.get("invitations")))
            self.lbl_strip_interviews.setText(fmt(st.get("interviews")))
            # Offers not tracked separately — show hired-ish unread as soft signal
            self.lbl_strip_offers.setText(fmt(st.get("unread_messages")))
            self.lbl_strip_updated.setText(
                ("Updated: " + (st.get("updated_at") or "—"))
            )
            if st.get("total_responses") is not None:
                self.lbl_strip_total.setText(fmt(st.get("total_responses")))
'''
    # insert before end of method (before capture_hotkey)
    text = text[:s1] + insert + "\n" + text[s1:]

path.write_text(text, encoding="utf-8")
compile(path.read_text(encoding="utf-8"), str(path), "exec")
print("ui patched OK", path.stat().st_size)
