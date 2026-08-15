# -*- coding: utf-8 -*-
"""Wire MainWindow to WebUiHost (ref04). ASCII-only generator."""
from pathlib import Path

path = Path(__file__).resolve().parent.parent / "radar" / "ui.py"
text = path.read_text(encoding="utf-8")

# --- Replace import block from PySide6 widgets through vacancy_delegate ---
start = text.find("from PySide6.QtCore import")
end = text.find("\ndef log(")
if start < 0 or end < 0:
    raise SystemExit("import markers missing")

new_imports = r'''from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QAction, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QMessageBox,
    QMenu,
    QSystemTrayIcon,
)

from radar.clipboard_util import set_clipboard
from radar.config import (
    ASSETS,
    LOG_PATH,
    NEGOTIATIONS_PATH,
    STATS_PATH,
    load_config,
    load_json,
    save_config,
)
from radar.chrome_ctl import launch_chrome_for_login, check_connection_fast
from radar.guides import GUIDE_HOTKEY, GUIDE_STATS
from radar.hotkeys import HotkeyManager, hotkey_label
from radar.queue_store import QueueStore
from radar.search_hh import open_vacancy_and_prepare, search_once, upgrade_cover_letters
from radar.cover_letter import _api_key, is_stale_template
from radar.sounds import beep_double, beep_once, beep_search_done, beep_six, beep_triple, sound_allowed
from radar.alerts import detect_employer_activity, format_activity_toast
from radar.negotiations_hh import apply_negotiations
from radar.autostart import is_autostart_enabled, set_autostart
from radar.queue_style import is_blue, pill_label, status_kind
from radar.stats_hh import fetch_stats
from radar.theme import THEME_LABELS, apply_app_font, apply_theme
from radar.themes import THEME_IDS
from radar.web_host import WebUiHost


'''
text = text[:start] + new_imports + text[end + 1 :]

# Remove leftover HH_HIGHLIGHT if present before def log
if "HH_HIGHLIGHT_ROLE" in text[: text.find("def log(")]:
    # already removed with imports
    pass

# --- __init__: after _build_ui keep refresh; add shortcuts ---
# Replace _build_ui and show_page
b0 = text.find("    def _build_ui(self):")
b1 = text.find("    def _build_tray(self):")
assert b0 > 0 and b1 > b0

build = r'''    def _build_ui(self):
        self._selected_url = ""
        self._log_lines = []
        self.web = WebUiHost(self)
        self.setCentralWidget(self.web)
        self._bind_web()
        QShortcut(QKeySequence("F5"), self, activated=self.run_search)
        QShortcut(QKeySequence("F9"), self, activated=self.run_stats)

    def _bind_web(self):
        w = self.web
        w.bind("ready", lambda _p: self._push_all_state())
        w.bind("search", lambda _p: self.run_search())
        w.bind("stats", lambda _p: self.run_stats())
        w.bind("select", lambda p: self._web_select(p.get("url") or ""))
        w.bind("open", lambda _p: self.open_selected())
        w.bind("mark", lambda p: self.mark_selected(str(p.get("status") or "")))
        w.bind("copyLetter", lambda _p: self.copy_selected_letter())
        w.bind("login", lambda _p: self.do_login_chrome())
        w.bind("check", lambda _p: self.do_check())
        w.bind("rebuildLetters", lambda _p: self.rebuild_letters())
        w.bind("captureHotkey", lambda _p: self.capture_hotkey())
        w.bind("testHotkey", lambda _p: self.test_hotkey())
        w.bind("resetHotkey", lambda _p: self.reset_hotkey())
        w.bind("guide", lambda p: self._web_guide(p.get("name") or ""))
        w.bind("setOpt", lambda p: self._web_set_opts(p))
        w.bind("setTheme", lambda p: self._web_set_theme(p.get("id") or "04"))
        w.bind("page", lambda _p: None)
        w.bind("_error", lambda p: self.append_log("UI: " + str((p or {}).get("error") or "")))

    def _push_all_state(self):
        self.refresh_queue_list()
        self.refresh_stats_labels()
        self._push_settings()
        self.web.push("hotkey", {"label": hotkey_label(self.cfg.get("hotkey") or "ctrl+alt+q")})
        if self._log_lines:
            self.web.push("log", {"lines": list(self._log_lines)})

    def _push_settings(self):
        self.web.push(
            "settings",
            {
                "sound_enabled": bool(self.cfg.get("sound_enabled", True)),
                "dnd": bool(self.cfg.get("dnd", False)),
                "minimize_previous": bool(self.cfg.get("minimize_previous", False)),
                "autostart_enabled": bool(self.cfg.get("autostart_enabled", False))
                or is_autostart_enabled(),
                "ui_theme": str(self.cfg.get("ui_theme") or "04"),
                "themes": [{"id": t, "label": THEME_LABELS.get(t, t)} for t in THEME_IDS],
            },
        )

    def _web_select(self, url: str):
        if not url:
            return
        self._selected_url = url
        self._push_detail(url)
        self.refresh_queue_list()

    def _web_guide(self, name: str):
        if name == "stats":
            self.show_text("Guide: HH stats", GUIDE_STATS)
        else:
            self.show_text("Guide: hotkey", GUIDE_HOTKEY)

    def _web_set_opts(self, p: dict):
        self.cfg["sound_enabled"] = bool(p.get("sound_enabled"))
        self.cfg["dnd"] = bool(p.get("dnd"))
        self.cfg["minimize_previous"] = bool(p.get("minimize_previous"))
        want = bool(p.get("autostart_enabled"))
        prev = bool(self.cfg.get("autostart_enabled", False))
        self.cfg["autostart_enabled"] = want
        save_config(self.cfg)
        if want != prev:
            self.append_log(set_autostart(want))

    def _web_set_theme(self, tid: str):
        self.cfg["ui_theme"] = str(tid or "04")
        save_config(self.cfg)
        apply_theme(QApplication.instance(), str(tid or "04"))
        self.append_log("Theme: " + THEME_LABELS.get(str(tid), str(tid)))

    def _push_detail(self, url: str):
        v = next((x for x in self.store.items if x.url == url), None)
        if not v:
            self.web.push("detail", None)
            return
        meta = []
        if v.remote:
            meta.append("Remote")
        if v.salary:
            meta.append(v.salary)
        if v.published:
            meta.append(str(v.published))
        skills = []
        for r in (v.reasons or [])[:8]:
            s = str(r).strip()
            if s and len(s) < 40:
                skills.append(s)
        facts = [
            {"label": "Location", "value": "Remote" if v.remote else "—"},
            {"label": "Employment", "value": "Full-time"},
            {"label": "Salary", "value": v.salary or "—"},
            {"label": "Status", "value": v.status or "—"},
            {"label": "Letter", "value": v.letter_source or "—"},
        ]
        self.web.push(
            "detail",
            {
                "url": v.url,
                "title": v.title or "",
                "company": v.company or "",
                "meta": meta,
                "score": int(v.score or 0),
                "facts": facts,
                "skills": skills,
                "letter": v.cover_letter or "",
            },
        )

    def show_page(self, index: int):
        name = {0: "queue", 1: "stats", 2: "settings"}.get(int(index), "queue")
        self.web.push("page", {"name": name})

'''
text = text[:b0] + build + text[b1:]

# --- append_log ---
a0 = text.find("    def append_log(self, msg: str):")
a1 = text.find("    def save_opts(self):")
if a0 < 0:
    raise SystemExit("append_log missing")
# save_opts may still exist - replace from append_log through on_theme_changed end
# Find refresh_queue_list as end of opts section
r0 = text.find("    def refresh_queue_list(self):")
assert r0 > a0

append_block = r'''    def append_log(self, msg: str):
        log(msg)
        self._log_lines.append(msg)
        if len(self._log_lines) > 400:
            self._log_lines = self._log_lines[-300:]
        if hasattr(self, "web"):
            self.web.push("log", {"line": msg, "lines": list(self._log_lines)})
        self.statusBar().showMessage(msg[:120])

    def save_opts(self):
        save_config(self.cfg)
        self._push_settings()

    def on_autostart_changed(self, _state: int = 0):
        pass

    def on_theme_changed(self, _index: int = 0):
        pass

'''
text = text[:a0] + append_block + text[r0:]

# --- refresh_queue_list + on_select + selected_url ---
r0 = text.find("    def refresh_queue_list(self):")
r1 = text.find("    def copy_selected_letter(self):")
assert r0 > 0 and r1 > r0

queue_block = r'''    def refresh_queue_list(self):
        prev = self.selected_url()
        new_count = 0
        visible = 0
        applied_n = 0
        active = self.store.active_url or self._opening_url or ""
        items = []
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
            title = v.title or ""
            if is_active and not title.startswith("\u2192 "):
                title = "\u2192 " + title
            meta_bits = []
            if v.remote:
                meta_bits.append("Remote")
            if v.salary:
                meta_bits.append(v.salary)
            if v.published:
                meta_bits.append(str(v.published))
            elif v.found_at:
                meta_bits.append(str(v.found_at)[:16].replace("T", " "))
            items.append(
                {
                    "url": v.url,
                    "title": title,
                    "company": v.company or "",
                    "meta": " \u00b7 ".join(meta_bits),
                    "score": int(v.score or 0),
                    "kind": kind,
                    "pill": pill_label(kind, v),
                    "blue": is_blue(v),
                }
            )
        restore = active or prev or self._selected_url
        if restore:
            self._selected_url = restore
        counts = {"total": visible, "new": new_count, "applied": applied_n}
        if hasattr(self, "web"):
            self.web.push(
                "queue",
                {"items": items, "counts": counts, "selectedUrl": self._selected_url or ""},
            )
            if self._selected_url:
                self._push_detail(self._selected_url)

    def on_select(self, row: int = -1):
        return

    def selected_url(self):
        return getattr(self, "_selected_url", None) or None

'''
# decode unicode in queue_block properly - write with real chars
queue_block = queue_block.replace("\\u2192 ", "\u2192 ").replace("\\u00b7 ", "\u00b7 ")
text = text[:r0] + queue_block + text[r1:]

# --- _select_url ---
s0 = text.find("    def _select_url(self, url: str)")
s1 = text.find("    def _open_vacancy(")
if s0 > 0 and s1 > s0:
    text = (
        text[:s0]
        + "    def _select_url(self, url: str) -> None:\n"
        + "        if not url:\n"
        + "            return\n"
        + "        self._selected_url = url\n"
        + "        self._push_detail(url)\n"
        + "\n"
        + text[s1:]
    )

# --- replace letter_view/detail/btn_search/btn_stats/lbl_hk references ---
replacements = [
    (
        'self.letter_view.setPlainText(v.cover_letter or "(?????? ????????????…)")\n'
        "        self.detail.setPlainText(\n"
        '            f"{v.title}\\n{v.company}\\n{v.url}\\n\\n????????… ?????? ???????, ???? ??? ?????????."\n'
        "        )\n"
        "        self.refresh_queue_list()",
        "self._selected_url = v.url\n"
        "        self.refresh_queue_list()\n"
        "        self._push_detail(v.url)",
    ),
]
# More robust: simple line replacements
text = text.replace("self.btn_search.setEnabled(False)", 'self.web.set_busy(search=True)')
text = text.replace("self.btn_search.setEnabled(True)", 'self.web.set_busy(search=False)')
text = text.replace("self.btn_stats.setEnabled(False)", 'self.web.set_busy(stats=True)')
text = text.replace("self.btn_stats.setEnabled(True)", 'self.web.set_busy(stats=False)')

# letter_view updates
import re
text = re.sub(
    r"self\.letter_view\.setPlainText\([^\n]+\)\n",
    "self._push_detail(getattr(v, 'url', self._selected_url) or self._selected_url or '')\n"
    if False
    else "",
    text,
)

# Fix letter_view more carefully with explicit patterns
text = text.replace(
    'self.letter_view.setPlainText(v.cover_letter or "(?????? ????????????…)")',
    "self._selected_url = v.url",
)
# remove detail.setPlainText blocks that remain - grep later

text = text.replace(
    "self.lbl_hk.setText(hotkey_label(combo))",
    'self.web.push("hotkey", {"label": hotkey_label(combo), "status": "Saved"})',
)
text = text.replace(
    'self.lbl_hk_status.setText("???? OK — ?????? ????????")',
    'self.web.push("hotkey", {"status": "Test OK"})',
)
text = text.replace(
    'self.lbl_hk_status.setText("??? ???????… (??????? ??? ??????? ?????? ????)")',
    'self.web.push("hotkey", {"status": "Waiting for key…" })',
)
text = text.replace(
    'self.lbl_hk_status.setText(f"?????????: {hotkey_label(combo)}")',
    'self.web.push("hotkey", {"label": hotkey_label(combo), "status": "Saved: " + hotkey_label(combo)})',
)
text = text.replace(
    'self.lbl_hk_status.setText("????: ??????? ?????? ? ??????? 5 ???…")',
    'self.web.push("hotkey", {"status": "Test: press hotkey within 5s…"})',
)
text = text.replace(
    'self.lbl_hk_status.setText("????: ?? ??????? ???????. ????????? ??????????.")',
    'self.web.push("hotkey", {"status": "Test: no key captured"})',
)
# remove setStyleSheet lines for hk status
text = re.sub(
    r"\s*self\.lbl_hk_status\.setStyleSheet\([^\n]+\)\n",
    "\n",
    text,
)

# refresh_stats_labels rewrite
rs0 = text.find("    def refresh_stats_labels(self, st=None):")
rs1 = text.find("    def capture_hotkey(self):")
assert rs0 > 0 and rs1 > rs0
stats_fn = r'''    def refresh_stats_labels(self, st=None):
        st = st or load_json(STATS_PATH, {})
        new_count = sum(
            1
            for v in self.store.items
            if v.status not in ("banned",) and status_kind(v) == "new"
        )
        applied_n = sum(
            1
            for v in self.store.items
            if v.status != "banned" and status_kind(v) == "apply"
        )
        visible = sum(1 for v in self.store.items if v.status != "banned")
        note = ""
        if st.get("stale"):
            note = "Showing last good values (incomplete fetch)"
        elif st.get("error") and not st.get("ok"):
            note = st.get("error") or ""
        payload = dict(st)
        payload["note"] = note
        if hasattr(self, "web"):
            self.web.push(
                "stats",
                {
                    "stats": payload,
                    "counts": {"total": visible, "new": new_count, "applied": applied_n},
                },
            )

'''
text = text[:rs0] + stats_fn + text[rs1:]

# Fix remaining letter_view / detail / list references
text = text.replace(
    "                    self.letter_view.setPlainText(v.cover_letter or \"\")\n",
    "                    self._push_detail(v.url)\n",
)
text = text.replace(
    "            row = self.list.currentRow()\n            if row >= 0:\n                self.on_select(row)\n",
    "            if self._selected_url:\n                self._push_detail(self._selected_url)\n",
)

# Remove detail.setPlainText if any left
text = re.sub(
    r"\s*self\.detail\.setPlainText\([\s\S]*?\)\n",
    "\n",
    text,
    count=5,
)

# mark_selected should work with selected_url
# open_selected already uses selected_url

# compile check
path.write_text(text, encoding="utf-8")
try:
    compile(path.read_text(encoding="utf-8"), str(path), "exec")
    print("OK", path.stat().st_size)
except SyntaxError as e:
    print("SYNTAX", e)
    raise
