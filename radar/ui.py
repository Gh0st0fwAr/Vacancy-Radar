# -*- coding: utf-8 -*-
"""Main VacancyRadar window."""
from __future__ import annotations

import sys
import threading
import traceback
from collections import deque
from datetime import datetime
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal, QObject
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
from radar.search_hh import generate_one_letter, open_vacancy_and_prepare, search_once, upgrade_cover_letters
from radar.cover_letter import _api_key, is_stale_template
from radar.sounds import (
    announce_search,
    beep_double,
    beep_once,
    beep_search_done,
    beep_six,
    beep_triple,
    sound_allowed,
)
from radar.alerts import detect_employer_activity, format_activity_toast
from radar.negotiations_hh import apply_negotiations
from radar.autostart import is_autostart_enabled, set_autostart
from radar.queue_style import (
    is_blue,
    letter_chip,
    letter_fact,
    letter_runtime_status,
    pill_label,
    status_kind,
)
from radar.stats_hh import fetch_stats
from radar.theme import THEME_LABELS, apply_app_font, apply_theme
from radar.themes import THEME_IDS
from radar.web_host import WebUiHost
from radar.win_hotkey import WindowsGlobalHotkey


def log(msg: str) -> None:
    line = f"{datetime.now().strftime('%H:%M:%S')} {msg}"
    try:
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass
    print(line, flush=True)


class BgBridge(QObject):
    """Lives on the GUI thread; worker threads emit into it safely."""
    ok = Signal(object)
    err = Signal(str)


class MainWindow(QMainWindow):
    hotkey_hit = Signal()
    hotkey_captured = Signal(str)
    search_progress = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VacancyRadar")
        # Large default; showMaximized in run() so type/spacing match browser prototype.
        self.resize(1600, 960)
        self.setMinimumSize(1280, 800)
        icon_path = ASSETS / "radar.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.cfg = load_config()
        self.store = QueueStore()
        self._bridges = []
        self._busy_search = False
        self._busy_stats = False
        self._busy_open = False
        self._opening_url = None
        self._open_seq = 0

        self.hotkeys = HotkeyManager(on_trigger=lambda: self.hotkey_hit.emit())
        self.hotkeys.set_hotkey(self.cfg.get("hotkey") or "ctrl+alt+q")
        self.hotkeys.start()
        self.hotkey_hit.connect(self.on_hotkey)
        self.hotkey_captured.connect(self.on_hotkey_captured)
        self.search_progress.connect(self._on_search_progress)
        self._activity_last_ts = 0.0
        self._activity_last_log_ts = 0.0
        self._letter_q: deque[str] = deque()
        self._letter_inflight: set[str] = set()
        self._letter_n = 0
        self._letter_done = 0
        self._letter_total = 0
        self._letter_beep_url = ""
        self._want_clear_check = False
        self._cc_boot_tries = 0
        self._win_hotkey = None

        self._build_ui()
        self._install_win_hotkey()
        self._build_tray()
        self.refresh_queue_list()
        self.refresh_stats_labels()

        self.search_timer = QTimer(self)
        self.search_timer.timeout.connect(self.run_search)
        self.stats_timer = QTimer(self)
        self.stats_timer.timeout.connect(self.run_stats)
        self._rearm_timers()

        self.statusBar().showMessage("Готово. Сначала: Войти в HH / Открыть Chrome")
        QTimer.singleShot(300, self.auto_boot_chrome)
        QTimer.singleShot(1200, self._kick_pending_letters)

    def _kick_pending_letters(self) -> None:
        urls = self._pending_letter_urls()
        if not urls:
            return
        self.append_log(f"Письма: {len(urls)} без текста Cursor — ставлю в очередь")
        self.enqueue_letters(urls)

    def auto_boot_chrome(self):
        self.append_log("Запускаю Chrome Radar для сессии HH…")
        try:
            msg = launch_chrome_for_login(open_login=True)
            self.append_log(msg)
        except Exception as e:
            self.append_log(f"Chrome: {e}")
        if self._want_clear_check:
            QTimer.singleShot(4000, self._boot_clear_check)

    def _boot_clear_check(self) -> None:
        if self._busy_search:
            return
        self._cc_boot_tries += 1
        ready = False
        try:
            msg = check_connection_fast()
            ready = "Связь OK" in str(msg)
            if not ready:
                self.append_log(f"Clear Check ждёт Chrome: {msg}")
        except Exception as e:
            self.append_log(f"Clear Check Chrome: {e}")
        if ready or self._cc_boot_tries >= 15:
            self.append_log("Автозапуск Clear Check…")
            self.run_clear_check()
            return
        QTimer.singleShot(1500, self._boot_clear_check)

    def _rearm_timers(self):
        search_ms = max(1, int(self.cfg.get("search_interval_min") or 15)) * 60 * 1000
        stats_ms = max(1, int(self.cfg.get("stats_interval_min") or 15)) * 60 * 1000
        self.search_timer.start(search_ms)
        # offset stats so it doesn't start in the same second as search
        self.stats_timer.stop()
        QTimer.singleShot(45_000, lambda: self.stats_timer.start(stats_ms))

    def _install_win_hotkey(self) -> None:
        combo = str(self.cfg.get("hotkey") or "ctrl+alt+q")
        if self._win_hotkey is not None:
            try:
                self._win_hotkey.stop()
            except Exception:
                pass
            self._win_hotkey = None
        self.hotkeys.suppress_fire = False
        try:
            hk = WindowsGlobalHotkey(self, combo, lambda: self.hotkey_hit.emit())
            if hk.start():
                self._win_hotkey = hk
                self.hotkeys.suppress_fire = True
                self.append_log(f"Глобальный хоткей (Windows): {combo} — работает и вне окна Radar")
                return
        except Exception as e:
            self.append_log(f"RegisterHotKey: {e}")
        self.append_log("Глобальный хоткей: fallback pynput (строго проверяю Ctrl)")

    def _pending_letter_urls(self, only=None):
        out = []
        for v in self.store.items:
            if only is not None and v.url not in only:
                continue
            if v.status in ("banned", "skipped", "applied"):
                continue
            src = (v.letter_source or "").strip().lower()
            if src == "cursor" and (v.cover_letter or "").strip():
                continue
            out.append(v.url)
        return out

    def enqueue_letters(self, urls, *, front: bool = False, beep_url: str = "") -> None:
        if beep_url:
            self._letter_beep_url = beep_url
        idle = not self._letter_q and not self._letter_inflight
        for u in urls or []:
            if not u or u in self._letter_inflight:
                continue
            if u in self._letter_q:
                if front:
                    self._letter_q.remove(u)
                    self._letter_q.appendleft(u)
                continue
            if front:
                self._letter_q.appendleft(u)
            else:
                self._letter_q.append(u)
        n = len(self._letter_q) + len(self._letter_inflight)
        if idle:
            self._letter_done = 0
            self._letter_total = n
        else:
            self._letter_total = max(
                self._letter_total, self._letter_done + n
            )
        if n:
            self._set_letter_activity("очередь")
            self.refresh_queue_list()
        self._letter_pump()

    def _letter_title(self, url: str, result=None) -> str:
        if result and (result or {}).get("title"):
            return str(result.get("title") or "")[:42]
        v = next((x for x in self.store.items if x.url == url), None)
        return ((v.title if v else "") or "")[:42]

    def _set_letter_activity(self, title: str, *, ok: bool | None = None, done: bool = False) -> None:
        total = max(1, int(self._letter_total or 0))
        cur = int(self._letter_done or 0)
        mark = "OK" if ok is True else ("FAIL" if ok is False else "…")
        line = f"Письма Cursor: [{cur}/{total}] {title} → {mark}"
        left = len(self._letter_q) + self._letter_n
        self._set_activity(busy=bool(left) and not done, line=line)

    def _letter_pump(self) -> None:
        max_w = max(1, min(int(self.cfg.get("cursor_letter_workers") or 5), 6))
        started = False
        while self._letter_n < max_w and self._letter_q:
            url = self._letter_q.popleft()
            self._letter_inflight.add(url)
            self._letter_n += 1
            started = True
            title = self._letter_title(url)
            self._set_letter_activity(title)
            self.append_log(f"Письмо Cursor [{self._letter_done}/{self._letter_total}] → «{title}»")
            timeout = int(self.cfg.get("cover_letter_timeout_sec") or 90) + 20
            self._run_bg(
                lambda u=url: generate_one_letter(self.store, u),
                lambda r, u=url: self._on_letter_one(u, r),
                on_fail=lambda err, u=url: self._on_letter_one(
                    u, {"ok": False, "error": err, "url": u}
                ),
                timeout_sec=timeout,
                on_timeout=lambda u=url: self._on_letter_one(
                    u, {"ok": False, "error": "timeout", "url": u}
                ),
            )
        if started:
            self.refresh_queue_list()

    def _on_letter_one(self, url: str, result) -> None:
        late = url not in self._letter_inflight
        if not late:
            self._letter_inflight.discard(url)
            self._letter_n = max(0, self._letter_n - 1)
            self._letter_done += 1
        ok = bool((result or {}).get("ok"))
        title = self._letter_title(url, result)
        if ok:
            self.append_log(
                f"Письмо готово [{self._letter_done}/{self._letter_total}]: {title}"
            )
            self.refresh_queue_list()
            target = self._letter_beep_url or self.store.active_url or self.selected_url()
            if url == target:
                v = next((x for x in self.store.items if x.url == url), None)
                if v and self._letter_ready(v):
                    self._copy_letter_ui(v.cover_letter)
                    self._push_detail(v.url)
                    if sound_allowed(self.cfg):
                        beep_double()
                        self.append_log("Письмо в буфере (двойной писк)")
            elif self._selected_url == url:
                self._push_detail(url)
        elif not late:
            v = next((x for x in self.store.items if x.url == url), None)
            if v and (v.letter_source or "") != "cursor":
                v.letter_source = "fail"
                try:
                    self.store.save()
                except Exception:
                    pass
            self.append_log(
                "Письмо FAIL "
                f"[{self._letter_done}/{self._letter_total}]: "
                + str((result or {}).get("error") or "")[:180]
            )
            self.refresh_queue_list()
        left = len(self._letter_q) + self._letter_n
        self._set_letter_activity(title, ok=ok, done=not left)
        if left:
            self._letter_pump()
        else:
            self._set_activity(
                busy=False,
                line=f"Письма Cursor: [{self._letter_done}/{self._letter_total}] готово",
            )

    def _build_ui(self):
        self._selected_url = ""
        self._log_lines = []
        zoom = float(self.cfg.get("ui_zoom") or 1.35)
        self.web = WebUiHost(self, zoom=zoom)
        self.setCentralWidget(self.web)
        self._bind_web()
        QShortcut(QKeySequence("F5"), self, activated=self.run_search)
        QShortcut(QKeySequence("F9"), self, activated=self.run_stats)

    def _bind_web(self):
        w = self.web
        w.bind("ready", lambda _p: self._push_all_state())
        w.bind("search", lambda _p: self.run_search())
        w.bind("clearCheck", lambda _p: self.run_clear_check())
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
        w.bind("uploadProfile", lambda p: self._web_upload_profile(p or {}))
        w.bind("clearProfile", lambda _p: self._web_clear_profile())
        w.bind("uploadPreferences", lambda p: self._web_upload_preferences(p or {}))
        w.bind("uploadReferences", lambda p: self._web_upload_references(p or {}))
        w.bind("savePack", lambda p: self._web_save_pack(p or {}))
        w.bind("loadPack", lambda p: self._web_load_pack(p or {}))
        w.bind("importPack", lambda p: self._web_import_pack(p or {}))
        w.bind("downloadPack", lambda p: self._web_download_pack(p or {}))

    def _push_all_state(self):
        self.refresh_queue_list()
        self.refresh_stats_labels()
        self._push_settings()
        self.web.push("hotkey", {"label": hotkey_label(self.cfg.get("hotkey") or "ctrl+alt+q")})
        if self._log_lines:
            self.web.push("log", {"lines": list(self._log_lines)})

    def _push_settings(self):
        from radar.scoring_state import ui_snapshot

        scoring = {}
        try:
            scoring = ui_snapshot()
        except Exception as e:
            self.append_log(f"Scoring snapshot: {e}")
        self.web.push(
            "settings",
            {
                "sound_enabled": bool(self.cfg.get("sound_enabled", True)),
                "dnd": bool(self.cfg.get("dnd", False)),
                "minimize_previous": bool(self.cfg.get("minimize_previous", False)),
                "autostart_enabled": bool(self.cfg.get("autostart_enabled", False))
                or is_autostart_enabled(),
                "ui_theme": str(self.cfg.get("ui_theme") or "04"),
                "scoring_mode": str(self.cfg.get("scoring_mode") or "cursor"),
                "clear_check_days": int(self.cfg.get("clear_check_days") or 7),
                "themes": [{"id": t, "label": THEME_LABELS.get(t, t)} for t in THEME_IDS],
                "scoring": scoring,
            },
        )
        if scoring:
            self.web.push("scoring", scoring)

    def _web_select(self, url: str):
        if not url:
            return
        self._selected_url = url
        self._push_detail(url)
        if hasattr(self, "web"):
            self.web.push("queue", {"selectedUrl": url})

    def _web_guide(self, name: str):
        if name == "stats":
            self.show_text("Guide: HH stats", GUIDE_STATS)
        else:
            self.show_text("Guide: hotkey", GUIDE_HOTKEY)

    def _web_set_opts(self, p: dict):
        # Update only keys present — avoid wiping sound when payload is partial.
        if "sound_enabled" in p:
            self.cfg["sound_enabled"] = bool(p.get("sound_enabled"))
        if "dnd" in p:
            self.cfg["dnd"] = bool(p.get("dnd"))
        if "minimize_previous" in p:
            self.cfg["minimize_previous"] = bool(p.get("minimize_previous"))
        if "scoring_mode" in p:
            mode = str(p.get("scoring_mode") or "cursor").strip().lower()
            self.cfg["scoring_mode"] = mode if mode in ("cursor", "rules") else "cursor"
            self.append_log("Scoring mode: " + str(self.cfg["scoring_mode"]))
        if "clear_check_days" in p:
            try:
                days = int(p.get("clear_check_days") or 7)
            except (TypeError, ValueError):
                days = 7
            self.cfg["clear_check_days"] = max(1, min(90, days))
        if "autostart_enabled" in p:
            want = bool(p.get("autostart_enabled"))
            prev = bool(self.cfg.get("autostart_enabled", False))
            self.cfg["autostart_enabled"] = want
            if want != prev:
                self.append_log(set_autostart(want))
        save_config(self.cfg)

    def _web_set_theme(self, tid: str):
        self.cfg["ui_theme"] = str(tid or "04")
        save_config(self.cfg)
        apply_theme(QApplication.instance(), str(tid or "04"))
        self.append_log("Theme: " + THEME_LABELS.get(str(tid), str(tid)))

    def _push_scoring(self, snap: Optional[dict] = None):
        if snap is None:
            try:
                from radar.scoring_state import ui_snapshot

                snap = ui_snapshot()
            except Exception as e:
                self.append_log(f"Scoring snapshot: {e}")
                snap = {}
        if hasattr(self, "web"):
            self.web.push("scoring", snap or {})

    def _scoring_upload_status(self, panel: str, status: str, error: str = ""):
        if hasattr(self, "web"):
            payload = {"panel": panel, "status": status}
            if error:
                payload["error"] = error
            self.web.push("scoringUpload", payload)

    def _web_upload_profile(self, p: dict):
        self._scoring_upload_status("profile", "loading")
        self.append_log("User Profile: Upload…")

        def job():
            from radar.scoring_actions import upload_profile_action

            return upload_profile_action(
                resume_b64=str(p.get("resume_b64") or ""),
                resume_filename=str(p.get("resume_filename") or ""),
                portfolio_url=str(p.get("portfolio_url") or ""),
                github_url=str(p.get("github_url") or ""),
                activity_sphere=str(p.get("activity_sphere") or ""),
                cfg=self.cfg,
            )

        def ok(result):
            snap = (result or {}).get("snapshot") or {}
            self._push_scoring(snap)
            self._scoring_upload_status("profile", "ok")
            if (result or {}).get("noop"):
                self.append_log("User Profile: уже актуально (noop)")
            else:
                self.append_log("User Profile: анализ Cursor завершён")

        def fail(err: str):
            self._scoring_upload_status("profile", "error", err or "fail")
            self.append_log("User Profile FAIL: " + (err or "").splitlines()[0][:200])

        self._run_bg(job, ok, fail, timeout_sec=180)

    def _web_clear_profile(self):
        try:
            from radar.scoring_actions import clear_profile_action

            result = clear_profile_action()
            self._push_scoring((result or {}).get("snapshot"))
            self.append_log("User Profile: cleared")
        except Exception as e:
            self.append_log(f"User Profile clear FAIL: {e}")

    def _web_upload_preferences(self, p: dict):
        self._scoring_upload_status("preferences", "loading")
        self.append_log("Preferences: Upload…")
        prefs = p.get("preferences") or {}

        def job():
            from radar.scoring_actions import upload_preferences_action

            return upload_preferences_action(prefs, cfg=self.cfg)

        def ok(result):
            self._push_scoring((result or {}).get("snapshot"))
            self._scoring_upload_status("preferences", "ok")
            if (result or {}).get("noop"):
                self.append_log("Preferences: уже актуально (noop)")
            else:
                self.append_log("Preferences: калибровка Cursor завершена")

        def fail(err: str):
            self._scoring_upload_status("preferences", "error", err or "fail")
            self.append_log("Preferences FAIL: " + (err or "").splitlines()[0][:200])

        self._run_bg(job, ok, fail, timeout_sec=180)

    def _web_upload_references(self, p: dict):
        self._scoring_upload_status("references", "loading")
        self.append_log("Vacancy References: Upload…")
        urls = p.get("urls") or []

        def job():
            from radar.scoring_actions import upload_references_action

            return upload_references_action(urls, cfg=self.cfg)

        def ok(result):
            self._push_scoring((result or {}).get("snapshot"))
            self._scoring_upload_status("references", "ok")
            if (result or {}).get("noop"):
                self.append_log("References: уже актуально (noop)")
            else:
                self.append_log("References: калибровка Cursor завершена")

        def fail(err: str):
            self._scoring_upload_status("references", "error", err or "fail")
            self.append_log("References FAIL: " + (err or "").splitlines()[0][:200])

        self._run_bg(job, ok, fail, timeout_sec=300)

    def _web_save_pack(self, p: dict):
        name = str(p.get("name") or "").strip()
        if not name:
            self.append_log("Saved profiles: пустое имя")
            return

        def job():
            from radar.scoring_actions import save_pack_action

            return save_pack_action(name)

        def ok(result):
            self._push_scoring((result or {}).get("snapshot"))
            self.append_log(f"Saved profiles: сохранён «{name}»")

        def fail(err: str):
            self.append_log("Saved profiles SAVE FAIL: " + (err or "").splitlines()[0][:200])

        self._run_bg(job, ok, fail, timeout_sec=60)

    def _web_load_pack(self, p: dict):
        name = str(p.get("name") or "").strip()
        if not name:
            self.append_log("Saved profiles: выберите профиль")
            return

        def job():
            from radar.scoring_actions import load_pack_action

            return load_pack_action(name)

        def ok(result):
            self._push_scoring((result or {}).get("snapshot"))
            self.append_log(f"Saved profiles: загружен «{name}»")

        def fail(err: str):
            self.append_log("Saved profiles LOAD FAIL: " + (err or "").splitlines()[0][:200])

        self._run_bg(job, ok, fail, timeout_sec=60)

    def _web_import_pack(self, p: dict):
        b64 = str(p.get("pack_b64") or "")
        filename = str(p.get("filename") or "pack.json")
        if not b64:
            self.append_log("Saved profiles: нет файла")
            return

        def job():
            from radar.scoring_actions import import_pack_b64_action

            return import_pack_b64_action(filename, b64)

        def ok(result):
            self._push_scoring((result or {}).get("snapshot"))
            self.append_log(f"Saved profiles: импортирован {filename}")

        def fail(err: str):
            self.append_log("Saved profiles IMPORT FAIL: " + (err or "").splitlines()[0][:200])

        self._run_bg(job, ok, fail, timeout_sec=60)

    def _web_download_pack(self, p: dict):
        """Save current config (or named pack) to a user-chosen JSON file."""
        from PySide6.QtWidgets import QFileDialog

        name = str(p.get("name") or "").strip()
        try:
            from radar.scoring_actions import save_pack_action
            from radar.profile_packs import export_pack_to_path, list_packs

            # Ensure a pack exists: use name, or snapshot as "current"
            pack_name = name or "current"
            if pack_name not in list_packs() or pack_name == "current" or not name:
                save_pack_action(pack_name)
            default = f"{pack_name}.json"
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Download config",
                default,
                "JSON (*.json)",
            )
            if not path:
                return
            export_pack_to_path(pack_name, path)
            self._push_scoring()
            self.append_log(f"Saved profiles: скачан {path}")
        except Exception as e:
            self.append_log(f"Saved profiles DOWNLOAD FAIL: {e}")

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
        score_src = ""
        for r in v.reasons or []:
            rs = str(r)
            if rs.startswith("score:"):
                score_src = rs.replace("score:", "", 1)
                break
        facts = [
            {"label": "Scoring", "value": score_src or "?"},
            {"label": "Location", "value": "Remote" if v.remote else "?"},
            {"label": "Employment", "value": "Full-time"},
            {"label": "Salary", "value": v.salary or "?"},
            {"label": "Status", "value": v.status or "?"},
            {
                "label": "Letter",
                "value": letter_fact(
                    letter_runtime_status(
                        v,
                        inflight=self._letter_inflight,
                        queued=set(self._letter_q),
                    )
                ),
            },
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
                "letterStatus": letter_runtime_status(
                    v,
                    inflight=self._letter_inflight,
                    queued=set(self._letter_q),
                ),
            },
        )

    def show_page(self, index: int):
        name = {0: "queue", 1: "stats", 2: "settings"}.get(int(index), "queue")
        self.web.push("page", {"name": name})

    def _build_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(self)
        icon_path = ASSETS / "radar.ico"
        if icon_path.exists():
            self.tray.setIcon(QIcon(str(icon_path)))
        else:
            self.tray.setIcon(self.windowIcon())
        menu = QMenu()
        act_show = QAction("Показать", self)
        act_show.triggered.connect(self.show_normal_raise)
        act_search = QAction("Искать сейчас", self)
        act_search.triggered.connect(self.run_search)
        act_quit = QAction("Выход", self)
        act_quit.triggered.connect(self.quit_app)
        menu.addAction(act_show)
        menu.addAction(act_search)
        menu.addSeparator()
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()
        self.tray.setToolTip("VacancyRadar")

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.show_normal_raise()

    def show_normal_raise(self):
        """Показать Radar, сохраняя fullscreen / maximize (без showNormal())."""
        state = self.windowState()
        if state & Qt.WindowMinimized:
            # Снять только Minimized, не трогая FullScreen/Maximized.
            self.setWindowState(state & ~Qt.WindowMinimized)
        self.show()
        self.raise_()
        self.activateWindow()

    def _minimize_all_except_radar_chrome(self):
        """Minimize every visible window except Chrome and VacancyRadar, then Z-order: Chrome > Radar."""
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            self_hwnd = int(self.winId())
            chrome_hwnd = None
            hwnds_to_minimize = []

            @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
            def enum_cb(hwnd, _):
                nonlocal chrome_hwnd
                if not user32.IsWindowVisible(hwnd):
                    return True
                if hwnd == self_hwnd:
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length == 0:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = (buf.value or "").lower()
                if not title or title == "program manager":
                    return True
                if "chrome" in title or "hh.ru" in title or "headhunter" in title:
                    chrome_hwnd = hwnd
                    return True
                hwnds_to_minimize.append(hwnd)
                return True

            user32.EnumWindows(enum_cb, 0)

            SW_MINIMIZE = 6
            for hwnd in hwnds_to_minimize:
                user32.ShowWindow(hwnd, SW_MINIMIZE)

            state = self.windowState()
            if state & Qt.WindowMinimized:
                self.setWindowState(state & ~Qt.WindowMinimized)
            self.show()
            self.raise_()

            if chrome_hwnd:
                SW_RESTORE = 9
                if user32.IsIconic(chrome_hwnd):
                    user32.ShowWindow(chrome_hwnd, SW_RESTORE)
                user32.SetForegroundWindow(chrome_hwnd)
        except Exception:
            pass

    def append_log(self, msg: str):
        log(msg)
        if not hasattr(self, "_log_lines"):
            self._log_lines = []
        self._log_lines.append(msg)
        if len(self._log_lines) > 400:
            self._log_lines = self._log_lines[-300:]
        if hasattr(self, "web"):
            self.web.push("log", {"line": msg, "lines": list(self._log_lines)})
        self.statusBar().showMessage(msg[:120])

    def _on_search_progress(self, msg: str) -> None:
        """GUI-thread only. Throttle WebEngine updates so Clear Check doesn't freeze Windows."""
        import time as _time

        now = _time.monotonic()
        s = (msg or "").lstrip()
        detail = s.startswith("[") or s.startswith("письмо") or s.startswith("+")
        phase = not detail
        if phase or now - self._activity_last_ts >= 0.35:
            self._activity_last_ts = now
            self._set_activity(busy=True, line=msg)
        if phase or now - self._activity_last_log_ts >= 2.0:
            self._activity_last_log_ts = now
            self.append_log(msg)

    def _set_activity(self, *, busy: bool, line: str = "") -> None:
        if hasattr(self, "web"):
            self.web.push("activity", {"busy": bool(busy), "line": line or ""})
        if line:
            self.statusBar().showMessage(line[:120])

    def save_opts(self):
        save_config(self.cfg)
        if hasattr(self, "web"):
            self._push_settings()

    def on_autostart_changed(self, _state: int = 0):
        pass

    def on_theme_changed(self, _index: int = 0):
        pass

    def refresh_queue_list(self):
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
            if is_active and not title.startswith("→ "):
                title = "→ " + title
            meta_bits = []
            if v.remote:
                meta_bits.append("Remote")
            if v.salary:
                meta_bits.append(v.salary)
            if v.published:
                meta_bits.append(str(v.published))
            elif v.found_at:
                meta_bits.append(str(v.found_at)[:16].replace("T", " "))
            letter_st = letter_runtime_status(
                v,
                inflight=self._letter_inflight,
                queued=set(self._letter_q),
            )
            items.append(
                {
                    "url": v.url,
                    "title": title,
                    "company": v.company or "",
                    "meta": " · ".join(meta_bits),
                    "score": int(v.score or 0),
                    "kind": kind,
                    "pill": pill_label(kind, v),
                    "letter": letter_chip(letter_st),
                    "letterStatus": letter_st,
                    "blue": is_blue(v),
                }
            )
        restore = prev or active or getattr(self, "_selected_url", "") or ""
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

    def copy_selected_letter(self):
        url = self.selected_url()
        if not url:
            self.append_log("Нет выбранной вакансии для копирования письма")
            return
        v = next((x for x in self.store.items if x.url == url), None)
        if not v or not v.cover_letter:
            self.append_log("Письмо пустое")
            return
        if self._copy_letter_ui(v.cover_letter):
            self.append_log("Письмо скопировано (только контакты + текст)")
        else:
            self.append_log("Не удалось скопировать письмо")

    def mark_selected(self, status: str):
        url = self.selected_url()
        if not url:
            return
        self.store.mark(url, status)
        self.refresh_queue_list()
        self.append_log(f"Статус {status}: {url}")

    def open_selected(self):
        url = self.selected_url()
        if not url:
            v = self.store.next_unvisited()
        else:
            v = next((x for x in self.store.items if x.url == url), None)
        if not v:
            self.append_log("Нечего открывать")
            return
        self._open_vacancy(v)

    def on_hotkey(self):
        if getattr(self, "_hk_test_mode", False):
            self._hk_test_mode = False
            self.web.push("hotkey", {"status": "Тест OK — хоткей сработал"})

            self.append_log("Тест хоткея: OK")
            return
        if self._busy_open:
            return
        if sound_allowed(self.cfg):
            beep_once()
        self._minimize_all_except_radar_chrome()
        threading.Thread(target=self._hotkey_purge_async, daemon=True).start()
        v = self.store.open_next()
        if not v:
            self.append_log("Очередь пуста — сначала «Искать сейчас»")
            self.show_normal_raise()
            return
        try:
            self._open_vacancy(v, raise_radar=False)
        except Exception as e:
            self._finish_open()
            self.append_log(f"Хоткей: {e}")

    def _hotkey_purge_async(self) -> None:
        try:
            purged = self.store.purge_refused(persist=True)
            if purged:
                QTimer.singleShot(0, lambda n=purged: self._hotkey_purged(n))
        except Exception:
            pass

    def _hotkey_purged(self, purged: int) -> None:
        self.append_log(f"Убрано отказов из очереди: {purged}")
        self.refresh_queue_list()

    def _copy_letter_ui(self, text: str, *, block: bool = False) -> bool:
        """Copy letter. Default: Qt sync + clipboard async (не блокирует Chrome)."""
        from radar.clipboard_util import set_clipboard, set_clipboard_async

        ok = False
        try:
            QApplication.clipboard().setText(text or "")
            ok = True
        except Exception:
            pass
        if block:
            if set_clipboard(text or ""):
                ok = True
        else:
            set_clipboard_async(text or "")
            if (text or "").strip():
                ok = True
        return ok

    def _select_url(self, url: str) -> None:
        if not url:
            return
        self._selected_url = url
        self._push_detail(url)

    def _letter_ready(self, v) -> bool:
        text = (v.cover_letter or "").strip()
        if not text:
            return False
        if is_stale_template(text):
            return False
        # On Cursor branch: only Cursor-generated letters count as ready.
        want_cursor = bool(self.cfg.get("cover_letter_via_cursor", True)) and not bool(
            self.cfg.get("python_only", False)
        )
        if want_cursor and (v.letter_source or "") != "cursor":
            return False
        return True

    def _open_vacancy(self, v, *, raise_radar: bool = True):
        if self._busy_open:
            self.append_log("Уже открываю другую — подождите")
            return
        self._busy_open = True
        self._opening_url = v.url
        self._open_seq += 1
        open_seq = self._open_seq
        QTimer.singleShot(10_000, lambda seq=open_seq: self._open_busy_watchdog(seq))

        if v.status == "new":
            v.status = "visited"
            self.append_log("Статус: просмотрено (серый). Applied — после Update Stats, если отклик есть на HH.")
        self.store.set_active(v.url, persist=False)
        threading.Thread(target=self.store.save, daemon=True).start()

        letter_ok = self._letter_ready(v)
        if letter_ok:
            self._copy_letter_ui(v.cover_letter or "", block=False)

        self._selected_url = v.url
        QTimer.singleShot(0, lambda u=v.url: (self._push_detail(u), self.refresh_queue_list()))

        if letter_ok:
            self.append_log(f"→ {v.title} · " + ("письмо в буфере" if (v.cover_letter or "").strip() else "буфер…"))
        else:
            self.append_log(f"→ {v.title} · письмо генерируется (двойной писк, когда будет готово)")
            self.enqueue_letters([v.url], front=True, beep_url=v.url)

        def chrome_job():
            import time as _time

            from radar.chrome_ctl import open_url_fast

            t0 = _time.perf_counter()
            ok = False
            try:
                ok = bool(open_url_fast(v.url))
            except Exception:
                ok = False
            return {"ok": ok, "ms": (_time.perf_counter() - t0) * 1000.0}

        def chrome_done(result):
            if open_seq != self._open_seq:
                self._finish_open()
                return
            opened = bool((result or {}).get("ok"))
            open_ms = float((result or {}).get("ms") or 0.0)
            self.append_log(f"▶ Chrome {'OK' if opened else 'FAIL'} за {open_ms:.0f} мс")
            threading.Thread(target=self.store.save, daemon=True).start()
            if not opened:
                self._run_bg(
                    lambda: open_vacancy_and_prepare(v),
                    lambda r: self._on_opened(r, open_seq),
                    on_fail=lambda err: self._on_open_fail(err, open_seq),
                    timeout_sec=12,
                    on_timeout=lambda: self._on_open_timeout(open_seq),
                )
            else:
                self._finish_open()
                if raise_radar:
                    self.show_normal_raise()

        def chrome_fail(err: str):
            if open_seq != self._open_seq:
                self._finish_open()
                return
            self.append_log("Chrome: " + (err or "").splitlines()[0])
            self._run_bg(
                lambda: open_vacancy_and_prepare(v),
                lambda r: self._on_opened(r, open_seq),
                on_fail=lambda e: self._on_open_fail(e, open_seq),
                timeout_sec=12,
                on_timeout=lambda: self._on_open_timeout(open_seq),
            )

        def chrome_timeout():
            if open_seq != self._open_seq:
                self._finish_open()
                return
            self.append_log("Chrome: таймаут открытия — снимаю блокировку хоткея")
            self._finish_open()

        self._run_bg(
            chrome_job,
            chrome_done,
            on_fail=chrome_fail,
            timeout_sec=8,
            on_timeout=chrome_timeout,
        )

    def _open_busy_watchdog(self, open_seq: int) -> None:
        if open_seq != self._open_seq:
            return
        if self._busy_open:
            self.append_log("Watchdog: снимаю блокировку хоткея")
            self._finish_open()

    def _finish_open(self):
        self._busy_open = False
        self._opening_url = None

    def _on_opened(self, result, open_seq: int):
        if open_seq != self._open_seq:
            return
        url = (result or {}).get("url") or self._opening_url
        if url:
            v = next((x for x in self.store.items if x.url == url), None)
            if v and self._letter_ready(v):
                self._copy_letter_ui(v.cover_letter)
        self.append_log((result or {}).get("message") or str(result))
        self._finish_open()
        if url:
            self._select_url(url)

    def _on_open_fail(self, err, open_seq: int):
        if open_seq != self._open_seq:
            return
        self.append_log(f"Не открылось: {(err or '').splitlines()[0]}")
        self._finish_open()

    def _on_open_timeout(self, open_seq: int):
        if open_seq != self._open_seq:
            return
        self._open_seq += 1
        self.append_log("Открытие зависло — снимаю блокировку хоткея. Проверьте вкладку Chrome.")
        self._finish_open()

    def do_login_chrome(self):
        self.append_log("Открываю Chrome…")
        try:
            msg = launch_chrome_for_login(open_login=True)
            self.append_log(msg)
        except Exception as e:
            self.append_log(f"Ошибка Chrome: {e}")

    def do_check(self):
        self.append_log("Проверяю связь…")
        try:
            msg = check_connection_fast()
            self.append_log(msg)
            if "OK" in msg:
                QMessageBox.information(self, "Связь", msg)
            else:
                QMessageBox.warning(self, "Связь", msg)
        except Exception as e:
            self.append_log(f"Связь FAIL: {e}")
            QMessageBox.warning(self, "Связь", str(e))

    def run_search(self):
        self._run_search_impl(clear_check=False)

    def run_clear_check(self):
        self._run_search_impl(clear_check=True)

    def _run_search_impl(self, *, clear_check: bool):
        if self._busy_search:
            self.append_log("Поиск уже идёт…")
            return
        self._busy_search = True
        self.web.set_busy(search=True)
        if clear_check:
            days = int(self.cfg.get("clear_check_days") or 7)
            self.append_log(f"Clear Check: SERP за последние {days} дн.…")
            self._set_activity(busy=True, line=f"Clear Check: загрузка SERP ({days} дн.)…")
        else:
            self.append_log("Поиск HH… (Cursor parallel + письма)")
            self._set_activity(busy=True, line="Поиск: загрузка вакансий с HH…")

        def on_prog(msg: str) -> None:
            self.search_progress.emit(msg)

        def job():
            return search_once(self.store, clear_check=clear_check, on_progress=on_prog)

        timeout = int(self.cfg.get("clear_check_timeout_sec") or 900) if clear_check else 600
        self._run_bg(
            job,
            self._on_search_done,
            self._on_search_fail,
            timeout_sec=timeout,
            on_timeout=self._on_search_timeout,
        )

    def _on_search_timeout(self):
        self._busy_search = False
        self.web.set_busy(search=False)
        self._set_activity(busy=False, line="Поиск: таймаут")
        self.append_log("Поиск: таймаут. Проверьте, что Chrome Radar открыт и вы залогинены.")

    def _on_search_fail(self, err: str):
        self._busy_search = False
        self.web.set_busy(search=False)
        self._set_activity(busy=False, line="Поиск: ошибка")
        self.append_log("Ошибка поиска: " + (err or "").splitlines()[0])

    def _on_search_done(self, result):
        self._busy_search = False
        self.web.set_busy(search=False)
        if not result or not result.get("ok"):
            self._set_activity(busy=False, line="Поиск: ошибка")
            self.append_log("Поиск: " + ((result or {}).get("error") or "ошибка"))
            return
        added = result.get("added") or []
        mode = "Clear Check" if result.get("clear_check") else "Поиск"
        done_line = (
            f"{mode} готово: +{len(added)} новых, {result.get('elapsed_sec', '?')}с"
        )
        self._set_activity(busy=False, line=done_line)
        self.append_log(
            f"{mode} OK. Новых: {len(added)}, проверено: {result.get('checked')}, "
            f"SERP стр.: {result.get('serp_pages', 0)}, deep: {result.get('deep_opened', 0)}, "
            f"{result.get('elapsed_sec', '?')}с"
        )
        self.refresh_queue_list()
        msg = announce_search(self.cfg, len(added))
        if msg:
            self.append_log(msg)
        purged = self.store.purge_refused(persist=True)
        if purged:
            self.append_log(f"Убрано отказов из очереди: {purged}")
            self.refresh_queue_list()
        if added:
            if hasattr(self, "tray"):
                self.tray.showMessage(
                    "VacancyRadar",
                    f"Новых вакансий: {len(added)} (лучшая {added[0].score}%)",
                    QSystemTrayIcon.Information,
                    8000,
                )
            self.show_normal_raise()
        pending = self._pending_letter_urls()
        if pending:
            self.enqueue_letters(pending)

    def rebuild_letters(self):
        self.append_log("Пересобираю сопроводительные…")
        self.enqueue_letters(self._pending_letter_urls())

    def _start_letter_upgrade(self, urls, *, beep_on_ready: bool = False, focus_url: str = ""):
        if urls is None:
            self.enqueue_letters(self._pending_letter_urls(), beep_url=focus_url)
        else:
            self.enqueue_letters(list(urls), front=bool(focus_url), beep_url=focus_url or "")

    def run_stats(self):
        if self._busy_stats:
            self.append_log("Статистика уже обновляется…")
            return
        self._busy_stats = True
        self.web.set_busy(stats=True)
        self._stats_prev = load_json(STATS_PATH, {})
        self.append_log("Обновляю статистику…")
        self._run_bg(
            fetch_stats,
            self._on_stats,
            self._on_stats_fail,
            timeout_sec=180,
            on_timeout=self._on_stats_timeout,
        )

    def _on_stats_timeout(self):
        self._busy_stats = False
        self.web.set_busy(stats=False)
        self.append_log("Статистика: таймаут. Chrome занят или не залогинен.")

    def _on_stats_fail(self, err: str):
        self._busy_stats = False
        self.web.set_busy(stats=False)
        self.append_log("Статистика: " + (err or "").splitlines()[0])

    def _notify_employer_activity(self, events):
        if not events:
            return
        body = format_activity_toast(events)
        self.append_log("ALERT HH: " + body.replace("\n", " | "))
        if sound_allowed(self.cfg):
            beep_six()
        if hasattr(self, "tray") and self.tray is not None:
            try:
                self.tray.showMessage(
                    "VacancyRadar · активность работодателя",
                    body,
                    QSystemTrayIcon.Warning,
                    20000,
                )
            except Exception:
                pass
        self.show_normal_raise()
        # Неблокирующий баннер в статусбаре + лог; модалку не ставим — не мешает откликам.
        self.statusBar().showMessage("⚠ " + body.replace("\n", " · "), 20000)

    def _on_stats(self, st):
        self._busy_stats = False
        self.web.set_busy(stats=False)
        st = st or {}
        prev = getattr(self, "_stats_prev", {}) or {}
        events = detect_employer_activity(prev, st)
        if not st.get("ok"):
            self.append_log(
                "Статистика: "
                + (st.get("error") or "не ок")
                + (" (сохранены прошлые цифры)" if st.get("stale") else "")
            )
        else:
            msg = "Статистика обновлена"
            if st.get("stale"):
                msg += " (частично, старые поля сохранены)"
            self.append_log(msg)
        self._sync_negotiations_from_stats(st)
        self.refresh_stats_labels(st)
        self._notify_employer_activity(events)

    def _sync_negotiations_from_stats(self, st: dict) -> None:
        """Apply HH negotiations list into queue (with disk fallback)."""
        neg = st.get("negotiations") if isinstance(st, dict) else None
        if not isinstance(neg, list) or not neg:
            cached = load_json(NEGOTIATIONS_PATH, {})
            neg = cached.get("items") if isinstance(cached, dict) else None
            if isinstance(neg, list) and neg:
                self.append_log(
                    f"Отклики HH: берём кэш ({len(neg)} шт.) — в ответе статистики списка не было"
                )
        if not isinstance(neg, list) or not neg:
            self.append_log("Отклики HH: список пуст — очередь не менялась")
            return
        try:
            sync = apply_negotiations(self.store, neg)
            self.refresh_queue_list()
            promo = int(sync.get("promoted") or 0)
            extra = f", просмотренных → Applied: {promo}" if promo else ""
            self.append_log(
                "Отклики HH → очередь: "
                f"+{sync.get('added', 0)} обновлено {sync.get('updated', 0)} "
                f"снято {sync.get('removed', 0)}{extra} (всего на HH: {sync.get('total', 0)})"
            )
        except Exception as e:
            self.append_log(f"Синхронизация откликов: {e}")

    def refresh_stats_labels(self, st=None):
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

    def capture_hotkey(self):
        self.web.push("hotkey", {"status": "Жду нажатие… (клавиши или боковая кнопка мыши)"})

        self.hotkeys.start_capture(lambda s: self.hotkey_captured.emit(s))

    def on_hotkey_captured(self, combo: str):
        self.cfg["hotkey"] = combo
        save_config(self.cfg)
        self.hotkeys.set_hotkey(combo)
        self._install_win_hotkey()
        self.web.push("hotkey", {"label": hotkey_label(combo)})
        self.web.push("hotkey", {"status": f"Сохранено: {hotkey_label(combo)}"})

        self.append_log(f"Хоткей назначен: {combo}")

    def reset_hotkey(self):
        self.on_hotkey_captured("ctrl+alt+q")

    def test_hotkey(self):
        self._hk_test_mode = True
        self.web.push("hotkey", {"status": "Тест: нажмите хоткей в течение 5 сек…"})

        QTimer.singleShot(5000, self._test_hk_timeout)

    def _test_hk_timeout(self):
        if getattr(self, "_hk_test_mode", False):
            self._hk_test_mode = False
            self.web.push("hotkey", {"status": "Тест: не поймали нажатие. Проверьте назначение."})


    def show_text(self, title: str, body: str):
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(body)
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()

    def _run_bg(self, fn, on_ok, on_fail=None, timeout_sec=None, on_timeout=None):
        bridge = BgBridge()
        self._bridges.append(bridge)
        done = {"flag": False, "timed_out": False}

        def finish_ok(result):
            # Если сработал UI-таймаут, всё равно применяем опоздавший результат
            # (иначе статистика/отклики «успешны», а очередь не обновляется).
            if done["flag"] and not done.get("timed_out"):
                return
            done["flag"] = True
            if done.get("timed_out"):
                self.append_log("Фоновая задача: опоздавший ответ — применяю результат")
            on_ok(result)

        def finish_err(err):
            if done["flag"] and not done.get("timed_out"):
                return
            done["flag"] = True
            if on_fail:
                on_fail(err)
            else:
                self.append_log((err or "").splitlines()[0])

        bridge.ok.connect(finish_ok)
        bridge.err.connect(finish_err)

        def run():
            try:
                bridge.ok.emit(fn())
            except Exception as e:
                bridge.err.emit(f"{e}\n{traceback.format_exc()}")

        threading.Thread(target=run, daemon=True).start()

        if timeout_sec and on_timeout:
            def _to():
                if not done["flag"]:
                    done["timed_out"] = True
                    done["flag"] = True
                    on_timeout()

            QTimer.singleShot(int(timeout_sec * 1000), _to)

    def closeEvent(self, event):
        if hasattr(self, "tray") and self.tray.isVisible():
            self.hide()
            self.tray.showMessage("VacancyRadar", "Работаю в трее", QSystemTrayIcon.Information, 2000)
            event.ignore()
            return
        self.quit_app()

    def quit_app(self):
        try:
            if self._win_hotkey is not None:
                self._win_hotkey.stop()
        except Exception:
            pass
        try:
            self.hotkeys.stop()
        except Exception:
            pass
        QApplication.instance().quit()


def run():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("VacancyRadar")
    apply_app_font(app)
    cfg0 = load_config()
    apply_theme(app, str(cfg0.get("ui_theme") or "04"))
    icon_path = ASSETS / "radar.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    win = MainWindow()
    if "--clear-check" in sys.argv:
        win._want_clear_check = True
        win.append_log("Флаг --clear-check: Clear Check после старта Chrome")
    win.showMaximized()
    return app.exec()
