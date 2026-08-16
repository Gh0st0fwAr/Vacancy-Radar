# -*- coding: utf-8 -*-
"""Main VacancyRadar window."""
from __future__ import annotations

import sys
import threading
import traceback
from datetime import datetime

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
from radar.search_hh import open_vacancy_and_prepare, search_once, upgrade_cover_letters
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
from radar.queue_style import is_blue, pill_label, status_kind
from radar.stats_hh import fetch_stats
from radar.theme import THEME_LABELS, apply_app_font, apply_theme
from radar.themes import THEME_IDS
from radar.web_host import WebUiHost


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

        self._build_ui()
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

    def auto_boot_chrome(self):
        self.append_log("Запускаю Chrome Radar для сессии HH…")
        try:
            msg = launch_chrome_for_login(open_login=True)
            self.append_log(msg)
        except Exception as e:
            self.append_log(f"Chrome: {e}")

    def _rearm_timers(self):
        search_ms = max(1, int(self.cfg.get("search_interval_min") or 15)) * 60 * 1000
        stats_ms = max(1, int(self.cfg.get("stats_interval_min") or 15)) * 60 * 1000
        self.search_timer.start(search_ms)
        # offset stats so it doesn't start in the same second as search
        self.stats_timer.stop()
        QTimer.singleShot(45_000, lambda: self.stats_timer.start(stats_ms))

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
                "scoring_mode": str(self.cfg.get("scoring_mode") or "cursor"),
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

    def _minimize_previous_if_needed(self):
        """Свернуть чужое окно, но не Chrome и не сам VacancyRadar (режим F11/maximize)."""
        if not self.cfg.get("minimize_previous"):
            return
        try:
            import ctypes
            from ctypes import wintypes

            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return
            # Не трогаем себя
            try:
                self_hwnd = int(self.winId())
                if hwnd == self_hwnd:
                    return
            except Exception:
                pass
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = (buf.value or "").lower()
            # Не сворачиваем Chrome / HH — иначе слетает fullscreen.
            if (
                "chrome" in title
                or "hh.ru" in title
                or "vacancyradar" in title
                or "headhunter" in title
            ):
                return
            user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE
        except Exception:
            return

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
            items.append(
                {
                    "url": v.url,
                    "title": title,
                    "company": v.company or "",
                    "meta": " · ".join(meta_bits),
                    "score": int(v.score or 0),
                    "kind": kind,
                    "pill": pill_label(kind, v),
                    "blue": is_blue(v),
                }
            )
        restore = active or prev or getattr(self, "_selected_url", "")
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
        if sound_allowed(self.cfg):
            beep_once()
        if self._busy_open:
            self.append_log("Хоткей: открытие ещё идёт — повтор игнор")
            return
        self.append_log("Хоткей сработал")
        self._minimize_previous_if_needed()
        purged = self.store.purge_refused(persist=True)
        if purged:
            self.append_log(f"Убрано отказов из очереди: {purged}")
            self.refresh_queue_list()
        v = self.store.open_next()
        if not v:
            self.append_log("Очередь пуста — сначала «Искать сейчас»")
            self.show_normal_raise()
            return
        # Не raise Radar до Chrome — иначе фокус уезжает с вкладки и кажется, что «долго».
        self._open_vacancy(v, raise_radar=False)

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
        QTimer.singleShot(2500, lambda seq=open_seq: self._open_busy_watchdog(seq))

        import time as _time

        from radar.chrome_ctl import open_url_fast

        # Chrome параллельно с указателем — не ждём PowerShell/диск.
        chrome_holder: dict = {}

        def _chrome_job():
            t0 = _time.perf_counter()
            try:
                chrome_holder["ok"] = bool(open_url_fast(v.url))
            except Exception:
                chrome_holder["ok"] = False
            chrome_holder["ms"] = (_time.perf_counter() - t0) * 1000.0

        chrome_thread = threading.Thread(target=_chrome_job, daemon=True)
        chrome_thread.start()

        if v.status == "new":
            v.status = "visited"
        self.store.set_active(v.url, persist=False)

        letter_ok = self._letter_ready(v)
        clip_ok = False
        if letter_ok:
            clip_ok = self._copy_letter_ui(v.cover_letter or "", block=False)

        self._selected_url = v.url
        self._push_detail(v.url)
        self.refresh_queue_list()
        self._select_url(v.url)
        QApplication.processEvents()

        if letter_ok:
            self.append_log(
                f"→ {v.title} · " + ("письмо в буфере" if clip_ok else "буфер — пишу в фоне")
            )
        else:
            self.append_log(f"→ {v.title} · письмо догонит позже (двойной писк + буфер)")

        chrome_thread.join(timeout=2.0)
        opened = bool(chrome_holder.get("ok"))
        open_ms = float(chrome_holder.get("ms") or 0.0)
        self.append_log(f"▶ Chrome {'OK' if opened else 'FAIL'} за {open_ms:.0f} мс")

        threading.Thread(target=self.store.save, daemon=True).start()

        if not opened:
            self._run_bg(
                lambda: open_vacancy_and_prepare(v),
                lambda result: self._on_opened(result, open_seq),
                on_fail=lambda err: self._on_open_fail(err, open_seq),
                timeout_sec=12,
                on_timeout=lambda: self._on_open_timeout(open_seq),
            )
        else:
            self._finish_open()
            if raise_radar:
                self.show_normal_raise()

        if not letter_ok:
            self._start_letter_upgrade([v.url], beep_on_ready=True, focus_url=v.url)

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
        if self._busy_search:
            self.append_log("Поиск уже идёт…")
            return
        self._busy_search = True
        self.web.set_busy(search=True)
        self.append_log("Поиск HH… (deep: полный текст каждой новой вакансии)")

        def job():
            return search_once(self.store)

        self._run_bg(
            job,
            self._on_search_done,
            self._on_search_fail,
            timeout_sec=90,
            on_timeout=self._on_search_timeout,
        )

    def _on_search_timeout(self):
        self._busy_search = False
        self.web.set_busy(search=False)
        self.append_log("Поиск: таймаут. Проверьте, что Chrome Radar открыт и вы залогинены.")

    def _on_search_fail(self, err: str):
        self._busy_search = False
        self.web.set_busy(search=False)
        self.append_log("Ошибка поиска: " + (err or "").splitlines()[0])

    def _on_search_done(self, result):
        self._busy_search = False
        self.web.set_busy(search=False)
        if not result or not result.get("ok"):
            self.append_log("Поиск: " + ((result or {}).get("error") or "ошибка"))
            return
        added = result.get("added") or []
        self.append_log(
            f"Поиск OK. Новых: {len(added)}, проверено: {result.get('checked')}, "
            f"полных страниц: {result.get('deep_opened', 0)}, "
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
            urls = result.get("letter_upgrade_urls") or [v.url for v in added]
            self._start_letter_upgrade(urls)

    def rebuild_letters(self):
        self.append_log("Пересобираю сопроводительные…")
        self._start_letter_upgrade(None)

    def _start_letter_upgrade(self, urls, *, beep_on_ready: bool = False, focus_url: str = ""):
        key_ok = bool(_api_key(self.cfg))
        if not key_ok:
            self.append_log(
                "Cursor API key не задан → письма локально под текст вакансии. "
                "Ключ: cursor.com/dashboard/integrations → data/config.json → cursor_api_key"
            )
        else:
            self.append_log("Дергаю Cursor SDK за уникальными письмами…")

        url_set = set(urls) if urls is not None else None
        focus = focus_url or ""

        def job():
            return upgrade_cover_letters(self.store, only_urls=url_set)

        def done(n):
            self.store.load()
            self.refresh_queue_list()
            target = focus or self.store.active_url or self.selected_url()
            if target:
                v = next((x for x in self.store.items if x.url == target), None)
                if v and self._letter_ready(v):
                    self._copy_letter_ui(v.cover_letter)
                    self._push_detail(v.url)
                    if beep_on_ready and sound_allowed(self.cfg):
                        beep_double()
                        self.append_log("Письмо готово → буфер (двойной писк)")
            if self._selected_url:
                self._push_detail(self._selected_url)
            self.append_log(f"Письма обновлены: {n}")

        self._run_bg(job, done, timeout_sec=600)

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
            self.append_log(
                "Отклики HH → очередь: "
                f"+{sync.get('added', 0)} обновлено {sync.get('updated', 0)} "
                f"снято {sync.get('removed', 0)} (всего на HH: {sync.get('total', 0)})"
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
    win.showMaximized()
    return app.exec()
