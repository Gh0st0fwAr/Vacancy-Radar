# -*- coding: utf-8 -*-
"""Wire MainWindow to WebUiHost. Pure ASCII source; writes UTF-8 ui.py."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UI = ROOT / "radar" / "ui.py"
BAK = UI.with_suffix(".py.bak_widgets")


def method_span(text: str, name: str) -> tuple[int, int]:
    pat = re.compile(rf"^    def {re.escape(name)}\(", re.M)
    m = pat.search(text)
    if not m:
        raise SystemExit(f"method missing: {name}")
    start = m.start()
    nxt = re.compile(r"^    def |^class |^def ", re.M)
    m2 = nxt.search(text, m.end())
    end = m2.start() if m2 else len(text)
    return start, end


def replace_method(text: str, name: str, body: str) -> str:
    start, end = method_span(text, name)
    if not body.endswith("\n"):
        body += "\n"
    return text[:start] + body + text[end:]


def replace_range_to_method(text: str, start_name: str, end_name: str, body: str) -> str:
    s0, _ = method_span(text, start_name)
    s1, _ = method_span(text, end_name)
    if not body.endswith("\n"):
        body += "\n"
    return text[:s0] + body + text[s1:]


NEW_IMPORTS = '''from PySide6.QtCore import Qt, QTimer, Signal, QObject
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

BUILD_BLOCK = r'''    def _build_ui(self):
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
            {"label": "Location", "value": "Remote" if v.remote else "?"},
            {"label": "Employment", "value": "Full-time"},
            {"label": "Salary", "value": v.salary or "?"},
            {"label": "Status", "value": v.status or "?"},
            {"label": "Letter", "value": v.letter_source or "?"},
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

APPEND_BLOCK = r'''    def append_log(self, msg: str):
        log(msg)
        if not hasattr(self, "_log_lines"):
            self._log_lines = []
        self._log_lines.append(msg)
        if len(self._log_lines) > 400:
            self._log_lines = self._log_lines[-300:]
        if hasattr(self, "web"):
            self.web.push("log", {"line": msg, "lines": list(self._log_lines)})
        self.statusBar().showMessage(msg[:120])

    def save_opts(self):
        save_config(self.cfg)
        if hasattr(self, "web"):
            self._push_settings()

    def on_autostart_changed(self, _state: int = 0):
        pass

    def on_theme_changed(self, _index: int = 0):
        pass

'''

ARROW = chr(0x2192) + " "
MDOT = " " + chr(0x00B7) + " "

QUEUE_BLOCK = f'''    def refresh_queue_list(self):
        prev = self.selected_url()
        new_count = 0
        visible = 0
        applied_n = 0
        active = self.store.active_url or getattr(self, "_opening_url", None) or ""
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
            if is_active and not title.startswith("{ARROW}"):
                title = "{ARROW}" + title
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
                {{
                    "url": v.url,
                    "title": title,
                    "company": v.company or "",
                    "meta": "{MDOT}".join(meta_bits),
                    "score": int(v.score or 0),
                    "kind": kind,
                    "pill": pill_label(kind, v),
                    "blue": is_blue(v),
                }}
            )
        restore = active or prev or getattr(self, "_selected_url", "")
        if restore:
            self._selected_url = restore
        counts = {{"total": visible, "new": new_count, "applied": applied_n}}
        if hasattr(self, "web"):
            self.web.push(
                "queue",
                {{"items": items, "counts": counts, "selectedUrl": self._selected_url or ""}},
            )
            if self._selected_url:
                self._push_detail(self._selected_url)

    def on_select(self, row: int = -1):
        return

'''

SELECT_URL = '''    def _select_url(self, url: str) -> None:
        if not url:
            return
        self._selected_url = url
        self._push_detail(url)

'''

STATS_FN = '''    def refresh_stats_labels(self, st=None):
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


def patch_open_vacancy(text: str) -> str:
    """Rewrite UI update section inside _open_vacancy (letter_view/detail)."""
    start, end = method_span(text, "_open_vacancy")
    body = text[start:end]
    # Find letter_view line and cut through _select_url call
    m = re.search(r"[ \t]*self\.letter_view\.setPlainText\(", body)
    if not m:
        # maybe already patched
        if "self._push_detail(v.url)" in body:
            return text
        raise SystemExit("_open_vacancy: letter_view missing")
    # Find _select_url(v.url) line end
    m2 = re.search(r"[ \t]*self\._select_url\(v\.url\)\n", body)
    if not m2:
        raise SystemExit("_open_vacancy: _select_url missing")
    replacement = (
        "        self._selected_url = v.url\n"
        "        self._push_detail(v.url)\n"
        "        self.refresh_queue_list()\n"
        "        self._select_url(v.url)\n"
    )
    # Also need to remove the refresh_queue_list that was between detail and _select_url
    # Our replacement includes refresh; remove old block including prior refresh.
    # Expand start back if refresh is only after detail - old block is letter.._select_url
    body = body[: m.start()] + replacement + body[m2.end() :]
    return text[:start] + body + text[end:]


def patch_letter_upgrade_done(text: str) -> str:
    start, end = method_span(text, "_start_letter_upgrade")
    body = text[start:end]
    body = re.sub(
        r"[ \t]*self\.letter_view\.setPlainText\([^\n]+\)\n",
        "                    self._push_detail(v.url)\n",
        body,
    )
    body = re.sub(
        r"[ \t]*row = self\.list\.currentRow\(\)\n"
        r"[ \t]*if row >= 0:\n"
        r"[ \t]*self\.on_select\(row\)\n",
        "            if self._selected_url:\n"
        "                self._push_detail(self._selected_url)\n",
        body,
    )
    return text[:start] + body + text[end:]


def scrub_simple(text: str) -> str:
    text = text.replace("self.btn_search.setEnabled(False)", "self.web.set_busy(search=True)")
    text = text.replace("self.btn_search.setEnabled(True)", "self.web.set_busy(search=False)")
    text = text.replace("self.btn_stats.setEnabled(False)", "self.web.set_busy(stats=True)")
    text = text.replace("self.btn_stats.setEnabled(True)", "self.web.set_busy(stats=False)")

    text = re.sub(
        r"self\.lbl_hk_status\.setText\((.+?)\)\n",
        r'self.web.push("hotkey", {"status": \1})\n',
        text,
    )
    text = re.sub(
        r"self\.lbl_hk\.setText\((.+?)\)\n",
        r'self.web.push("hotkey", {"label": \1})\n',
        text,
    )
    text = re.sub(r"[ \t]*self\.lbl_hk_status\.setStyleSheet\([^\n]+\)\n", "\n", text)
    return text


def main() -> None:
    if not BAK.exists():
        raise SystemExit("backup missing; restore widgets ui first")
    text = BAK.read_text(encoding="utf-8")

    start = text.find("from PySide6.QtCore import")
    end = text.find("\ndef log(")
    if start < 0 or end < 0:
        raise SystemExit("import markers missing")
    text = text[:start] + NEW_IMPORTS + text[end + 1 :]

    text = replace_range_to_method(text, "_build_ui", "_build_tray", BUILD_BLOCK)
    text = replace_range_to_method(text, "append_log", "refresh_queue_list", APPEND_BLOCK)
    text = replace_range_to_method(text, "refresh_queue_list", "copy_selected_letter", QUEUE_BLOCK)
    text = replace_method(text, "selected_url", '''    def selected_url(self):\n        return getattr(self, "_selected_url", None) or None\n\n''')
    text = replace_method(text, "_select_url", SELECT_URL)
    text = replace_method(text, "refresh_stats_labels", STATS_FN)

    text = patch_open_vacancy(text)
    text = patch_letter_upgrade_done(text)
    text = scrub_simple(text)

    leftovers = []
    for needle in (
        "self.list",
        "self.letter_view",
        "self.detail",
        "self.chk_",
        "self.cmb_",
        "self.lbl_",
        "self.btn_search",
        "self.btn_stats",
        "attach_shell",
        "HH_HIGHLIGHT",
        "theme_mod",
        "ui_shell",
        "VacancyCard",
        "QListWidget",
        "badge_for",
        "ScaleButton",
    ):
        if needle in text:
            leftovers.append(needle)

    UI.write_text(text, encoding="utf-8")
    compile(text, str(UI), "exec")
    print("COMPILE_OK", UI.stat().st_size)
    print("LEFTOVERS", leftovers)


if __name__ == "__main__":
    main()