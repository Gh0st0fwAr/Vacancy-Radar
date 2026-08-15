# -*- coding: utf-8 -*-
"""Main VacancyRadar window."""
from __future__ import annotations

import sys
import threading
import traceback
from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QAction, QColor, QFont, QIcon, QPainter, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStyle,
    QStyledItemDelegate,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
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
from radar.sounds import beep_double, beep_once, beep_six, beep_triple, sound_allowed
from radar.alerts import detect_employer_activity, format_activity_toast
from radar.negotiations_hh import apply_negotiations, badge_for
from radar.queue_style import ICON_SIZE, icon_for, is_blue, is_gray_apply, is_white
from radar.stats_hh import fetch_stats
from radar.theme import (
    ACCENT,
    DANGER,
    INVITE,
    INVITE_BG,
    OK,
    ScaleButton,
    TEXT,
    TEXT_DIM,
    TEXT_MUTED,
    THEME_QSS,
    WARN,
    apply_app_font,
)

# Маркер «активный указатель» (хоткей / последняя открытая).
ACTIVE_ROLE = Qt.UserRole + 1
HH_HIGHLIGHT_ROLE = Qt.UserRole + 2
POINTER_GREEN = QColor("#8dff9a")
SKIP_YELLOW = QColor(WARN)
INVITE_BLUE = QColor(INVITE)
INVITE_BG_COLOR = QColor(INVITE_BG)
WHITE_FG = QColor("#f5f7fa")
GRAY_APPLY = QColor("#9aa3ad")
GRAY_APPLY_BG = QColor("#2a3038")


class PointerGlowDelegate(QStyledItemDelegate):
    """Активная вакансия: крупный зелёный текст без glow (читаемость)."""

    def paint(self, painter: QPainter, option, index) -> None:
        if not index.data(ACTIVE_ROLE):
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        rect = option.rect.adjusted(12, 4, -12, -4)

        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect.adjusted(2, 1, -2, -1), QColor(45, 90, 55, 140))
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(option.rect.adjusted(2, 1, -2, -1), QColor(36, 60, 42, 100))
        else:
            painter.fillRect(option.rect.adjusted(2, 1, -2, -1), QColor(30, 48, 36, 70))

        text = index.data(Qt.DisplayRole) or ""
        font = QFont(option.font)
        item_font = index.data(Qt.FontRole)
        if isinstance(item_font, QFont):
            font = QFont(item_font)
        font.setBold(True)
        font.setPointSize(max(font.pointSize(), 16))
        painter.setFont(font)
        flags = int(Qt.AlignVCenter | Qt.AlignLeft | Qt.TextWordWrap)
        painter.setPen(POINTER_GREEN)
        painter.drawText(rect, flags, text)
        painter.restore()


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
        self.resize(1280, 820)
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
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter()
        layout.addWidget(splitter)

        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(12, 12, 8, 12)
        left_l.setSpacing(10)
        q_title = QLabel("Очередь (≥70%) — новые сверху")
        q_title.setObjectName("sectionTitle")
        left_l.addWidget(q_title)
        self.list = QListWidget()
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setTextElideMode(Qt.ElideRight)
        self.list.setWordWrap(True)
        self.list.setMinimumHeight(160)
        self.list.setIconSize(ICON_SIZE)
        self.list.setSpacing(6)
        self.list.setItemDelegate(PointerGlowDelegate(self.list))
        self.list.currentRowChanged.connect(self.on_select)
        left_l.addWidget(self.list, stretch=1)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        self.btn_open = ScaleButton("Открыть выбранную", role="primary")
        self.btn_open.clicked.connect(self.open_selected)
        self.btn_applied = ScaleButton("Откликнулся", role="ok")
        self.btn_applied.clicked.connect(lambda: self.mark_selected("applied"))
        self.btn_skip = ScaleButton("Скип", role="warn")
        self.btn_skip.clicked.connect(lambda: self.mark_selected("skipped"))
        self.btn_ban = ScaleButton("Удалить", role="danger")
        self.btn_ban.clicked.connect(lambda: self.mark_selected("banned"))
        for b in (self.btn_open, self.btn_applied, self.btn_skip, self.btn_ban):
            b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            btns.addWidget(b)
        left_l.addLayout(btns)
        splitter.addWidget(left)

        # Right column scrolls as a whole — nothing gets squashed on short/tall windows.
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QScrollArea.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        right_scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        right = QWidget()
        right.setMinimumWidth(420)
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(8, 12, 18, 12)
        right_l.setSpacing(12)
        right_l.setAlignment(Qt.AlignTop)

        act = QHBoxLayout()
        act.setSpacing(10)
        self.btn_login = ScaleButton("Войти в HH / Открыть Chrome", role="primary")
        self.btn_login.clicked.connect(self.do_login_chrome)
        self.btn_check = ScaleButton("Проверить связь")
        self.btn_check.clicked.connect(self.do_check)
        self.btn_search = ScaleButton("Искать сейчас", role="ok")
        self.btn_search.clicked.connect(self.run_search)
        self.btn_letters = ScaleButton("Пересобрать письма", role="ghost")
        self.btn_letters.clicked.connect(self.rebuild_letters)
        self.btn_stats = ScaleButton("Обновить статистику")
        self.btn_stats.clicked.connect(self.run_stats)
        for b in (self.btn_login, self.btn_check, self.btn_search, self.btn_letters, self.btn_stats):
            b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            act.addWidget(b)
        right_l.addLayout(act)

        stats_box = QGroupBox("Статистика HH (Frontend-резюме)")
        stats_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        sf = QFormLayout(stats_box)
        sf.setSpacing(10)
        sf.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self.lbl_active = QLabel("—")
        self.lbl_total = QLabel("—")
        self.lbl_inv = QLabel("—")
        self.lbl_interviews = QLabel("—")
        self.lbl_refusals = QLabel("—")
        self.lbl_unread = QLabel("—")
        self.lbl_views = QLabel("—")
        self.lbl_shows = QLabel("—")
        self.lbl_stats_at = QLabel("ещё не обновлялось")
        self.lbl_queue = QLabel("0")
        for lbl in (
            self.lbl_active,
            self.lbl_total,
            self.lbl_inv,
            self.lbl_interviews,
            self.lbl_refusals,
            self.lbl_unread,
            self.lbl_views,
            self.lbl_shows,
            self.lbl_queue,
        ):
            lbl.setObjectName("statsValue")
        self.lbl_stats_at.setObjectName("mutedLabel")
        self.lbl_stats_note = QLabel("")
        self.lbl_stats_note.setObjectName("mutedLabel")
        self.lbl_stats_note.setWordWrap(True)
        sf.addRow("Ожидание (активные):", self.lbl_active)
        sf.addRow("Всего в откликах:", self.lbl_total)
        sf.addRow("Приглашения:", self.lbl_inv)
        sf.addRow("Собеседования:", self.lbl_interviews)
        sf.addRow("Отказы:", self.lbl_refusals)
        sf.addRow("Непрочитанные чаты:", self.lbl_unread)
        sf.addRow("Просмотры резюме:", self.lbl_views)
        sf.addRow("Показы резюме:", self.lbl_shows)
        sf.addRow("В очереди (новые):", self.lbl_queue)
        sf.addRow("Обновлено:", self.lbl_stats_at)
        sf.addRow("", self.lbl_stats_note)
        right_l.addWidget(stats_box)

        guide_row = QHBoxLayout()
        guide_row.setSpacing(10)
        self.btn_guide = ScaleButton("Как подключить статистику HH", role="ghost")
        self.btn_guide.clicked.connect(lambda: self.show_text("Гайд: статистика HH", GUIDE_STATS))
        self.btn_guide_hk = ScaleButton("Про хоткей", role="ghost")
        self.btn_guide_hk.clicked.connect(lambda: self.show_text("Гайд: хоткей", GUIDE_HOTKEY))
        for b in (self.btn_guide, self.btn_guide_hk):
            b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            guide_row.addWidget(b)
        right_l.addLayout(guide_row)

        hk_box = QGroupBox("Хоткей")
        hk_box.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        hk_l = QVBoxLayout(hk_box)
        hk_l.setSpacing(10)
        self.lbl_hk = QLabel(hotkey_label(self.cfg.get("hotkey") or "ctrl+alt+q"))
        self.lbl_hk.setObjectName("hotkeyBadge")
        self.lbl_hk.setAlignment(Qt.AlignCenter)
        self.lbl_hk.setMinimumHeight(52)
        hk_l.addWidget(self.lbl_hk)
        hk_btns = QHBoxLayout()
        hk_btns.setSpacing(10)
        self.btn_set_hk = ScaleButton("Назначить хоткей", role="primary")
        self.btn_set_hk.clicked.connect(self.capture_hotkey)
        self.btn_test_hk = ScaleButton("Проверить хоткей")
        self.btn_test_hk.clicked.connect(self.test_hotkey)
        self.btn_reset_hk = ScaleButton("Сброс Ctrl+Alt+Q", role="ghost")
        self.btn_reset_hk.clicked.connect(self.reset_hotkey)
        for b in (self.btn_set_hk, self.btn_test_hk, self.btn_reset_hk):
            b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            hk_btns.addWidget(b)
        hk_l.addLayout(hk_btns)
        self.lbl_hk_status = QLabel("")
        self.lbl_hk_status.setObjectName("mutedLabel")
        self.lbl_hk_status.setWordWrap(True)
        hk_l.addWidget(self.lbl_hk_status)
        right_l.addWidget(hk_box)

        opt = QGroupBox("Опции")
        opt.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        ol = QVBoxLayout(opt)
        ol.setSpacing(8)
        self.chk_sound = QCheckBox("Звуковой сигнал (×3) при новой вакансии")
        self.chk_sound.setChecked(bool(self.cfg.get("sound_enabled", True)))
        self.chk_sound.stateChanged.connect(self.save_opts)
        self.chk_dnd = QCheckBox("DND — без звука")
        self.chk_dnd.setChecked(bool(self.cfg.get("dnd", False)))
        self.chk_dnd.stateChanged.connect(self.save_opts)
        self.chk_min = QCheckBox("Сворачивать предыдущее окно по хоткею")
        self.chk_min.setChecked(bool(self.cfg.get("minimize_previous", False)))
        self.chk_min.stateChanged.connect(self.save_opts)
        for chk in (self.chk_sound, self.chk_dnd, self.chk_min):
            chk.setMinimumHeight(36)
            ol.addWidget(chk)
        right_l.addWidget(opt)

        card_title = QLabel("Карточка вакансии")
        card_title.setObjectName("sectionTitle")
        right_l.addWidget(card_title)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMinimumHeight(140)
        self.detail.setMaximumHeight(220)
        self.detail.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        right_l.addWidget(self.detail)

        letter_row = QHBoxLayout()
        letter_title = QLabel("Сопроводительное (это и есть буфер)")
        letter_title.setObjectName("sectionTitle")
        letter_row.addWidget(letter_title, stretch=1)
        self.btn_copy_letter = ScaleButton("Скопировать письмо", role="primary")
        self.btn_copy_letter.clicked.connect(self.copy_selected_letter)
        self.btn_copy_letter.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        letter_row.addWidget(self.btn_copy_letter)
        right_l.addLayout(letter_row)
        self.letter_view = QTextEdit()
        self.letter_view.setReadOnly(True)
        self.letter_view.setMinimumHeight(200)
        self.letter_view.setMaximumHeight(360)
        self.letter_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        right_l.addWidget(self.letter_view)

        log_title = QLabel("Лог")
        log_title.setObjectName("sectionTitle")
        right_l.addWidget(log_title)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(120)
        self.log_view.setMaximumHeight(200)
        self.log_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        right_l.addWidget(self.log_view)
        right_l.addStretch(1)

        right_scroll.setWidget(right)
        splitter.addWidget(right_scroll)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setChildrenCollapsible(False)

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
        self.log_view.append(msg)
        self.log_view.moveCursor(QTextCursor.End)
        self.statusBar().showMessage(msg[:120])

    def save_opts(self):
        self.cfg["sound_enabled"] = self.chk_sound.isChecked()
        self.cfg["dnd"] = self.chk_dnd.isChecked()
        self.cfg["minimize_previous"] = self.chk_min.isChecked()
        save_config(self.cfg)

    def refresh_queue_list(self):
        prev = self.selected_url()
        self.list.clear()
        new_count = 0
        active = self.store.active_url or self._opening_url or ""
        for v in self.store.items:
            if v.status == "banned":
                continue
            badge = badge_for(v)
            if v.score and int(v.score) > 0:
                label = f"{badge}{v.score}%  {v.title}  ·  {v.company}"
            else:
                label = f"{badge}{v.title}  ·  {v.company}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, v.url)
            is_active = bool(active and v.url == active)
            item.setData(ACTIVE_ROLE, is_active)
            blue = is_blue(v)
            item.setData(HH_HIGHLIGHT_ROLE, blue)
            ic = icon_for(v)
            if not ic.isNull():
                item.setIcon(ic)
            # Цвета: синий ответ работодателя → серый мой отклик → белый новый → …
            if blue:
                item.setBackground(INVITE_BG_COLOR)
                item.setForeground(INVITE_BLUE)
                f = item.font()
                f.setBold(True)
                f.setPointSize(max(f.pointSize(), 15))
                item.setFont(f)
            elif is_gray_apply(v):
                item.setBackground(GRAY_APPLY_BG)
                item.setForeground(GRAY_APPLY)
                f = item.font()
                f.setPointSize(max(f.pointSize(), 13))
                item.setFont(f)
            elif is_white(v) or v.status == "new":
                new_count += 1
                item.setForeground(WHITE_FG)
                f = item.font()
                f.setBold(True)
                f.setPointSize(max(f.pointSize(), 14))
                item.setFont(f)
            elif v.status == "visited":
                item.setForeground(QColor(TEXT_DIM))
            elif v.status == "skipped":
                item.setForeground(SKIP_YELLOW)
                item.setText("⏭ " + item.text())
            # Зелёный только у активного указателя (поверх остальных цветов текста).
            if is_active:
                f = item.font()
                f.setBold(True)
                f.setPointSize(max(f.pointSize(), 16))
                item.setFont(f)
                item.setForeground(POINTER_GREEN)
                t = item.text()
                if t.startswith("⏭ "):
                    t = t[2:]
                if not t.startswith("→ "):
                    item.setText("→ " + t)
            self.list.addItem(item)
        self.lbl_queue.setText(str(new_count))
        # Сохранить выделение: сначала активный указатель, иначе прежний выбор.
        restore = active or prev
        if restore:
            self._select_url(restore)

    def on_select(self, row: int):
        if row < 0:
            return
        item = self.list.item(row)
        url = item.data(Qt.UserRole)
        v = next((x for x in self.store.items if x.url == url), None)
        if not v:
            return
        # Metadata only — never mixed into the cover letter / clipboard.
        self.detail.setPlainText(
            f"{v.title}\n{v.company}\n{v.url}\n\n"
            f"Score: {v.score}%\nЗП: {v.salary or 'не указана'}\nСтатус: {v.status}\n"
            f"Письмо: {v.letter_source or '—'}\n\n"
            f"Почему (только для тебя):\n" + "\n".join(v.reasons)
        )
        self.letter_view.setPlainText(v.cover_letter or "")

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

    def selected_url(self):
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else None

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
            self.lbl_hk_status.setText("Тест OK — хоткей сработал")
            self.lbl_hk_status.setStyleSheet(f"color: {OK}; font-weight: 700; font-size: 16px;")
            self.append_log("Тест хоткея: OK")
            return
        if sound_allowed(self.cfg):
            beep_once()
        if self._busy_open:
            self.append_log("Хоткей: снимаю залипшую блокировку и иду дальше")
            self._open_seq += 1
            self._finish_open()
        self.append_log("Хоткей сработал")
        self._minimize_previous_if_needed()
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
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item and item.data(Qt.UserRole) == url:
                self.list.setCurrentRow(i)
                self.list.scrollToItem(item)
                return

    def _letter_ready(self, v) -> bool:
        text = (v.cover_letter or "").strip()
        if not text:
            return False
        if is_stale_template(text):
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

        self.letter_view.setPlainText(v.cover_letter or "(письмо генерируется…)")
        self.detail.setPlainText(
            f"{v.title}\n{v.company}\n{v.url}\n\n"
            f"Score: {v.score}%\nЗП: {v.salary or 'не указана'}\nСтатус: {v.status}\n"
            f"Письмо: {v.letter_source or ('ожидается' if not letter_ok else '—')}\n\n"
            f"Почему (только для тебя):\n" + "\n".join(v.reasons)
        )
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
        self.btn_search.setEnabled(False)
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
        self.btn_search.setEnabled(True)
        self.append_log("Поиск: таймаут. Проверьте, что Chrome Radar открыт и вы залогинены.")

    def _on_search_fail(self, err: str):
        self._busy_search = False
        self.btn_search.setEnabled(True)
        self.append_log("Ошибка поиска: " + (err or "").splitlines()[0])

    def _on_search_done(self, result):
        self._busy_search = False
        self.btn_search.setEnabled(True)
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
        if added:
            if self.cfg.get("sound_enabled", True) and not self.cfg.get("dnd"):
                beep_triple()
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
                    self.letter_view.setPlainText(v.cover_letter or "")
                    if beep_on_ready and sound_allowed(self.cfg):
                        beep_double()
                        self.append_log("Письмо готово → буфер (двойной писк)")
            row = self.list.currentRow()
            if row >= 0:
                self.on_select(row)
            self.append_log(f"Письма обновлены: {n}")

        self._run_bg(job, done, timeout_sec=600)

    def run_stats(self):
        if self._busy_stats:
            self.append_log("Статистика уже обновляется…")
            return
        self._busy_stats = True
        self.btn_stats.setEnabled(False)
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
        self.btn_stats.setEnabled(True)
        self.append_log("Статистика: таймаут. Chrome занят или не залогинен.")

    def _on_stats_fail(self, err: str):
        self._busy_stats = False
        self.btn_stats.setEnabled(True)
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
        self.btn_stats.setEnabled(True)
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

        def fmt(v):
            return "—" if v is None else str(v)

        self.lbl_active.setText(fmt(st.get("active_responses")))
        self.lbl_total.setText(fmt(st.get("total_responses")))
        self.lbl_inv.setText(fmt(st.get("invitations")))
        self.lbl_interviews.setText(fmt(st.get("interviews")))
        self.lbl_refusals.setText(fmt(st.get("refusals")))
        self.lbl_unread.setText(fmt(st.get("unread_messages")))
        self.lbl_views.setText(fmt(st.get("resume_views")))
        self.lbl_shows.setText(fmt(st.get("resume_shows")))
        self.lbl_stats_at.setText(st.get("updated_at") or "ещё не обновлялось")
        note = ""
        if st.get("stale"):
            note = "Показаны последние успешные значения (последний съём был неполным)"
        elif st.get("error") and not st.get("ok"):
            note = st.get("error")
        self.lbl_stats_note.setText(note)

    def capture_hotkey(self):
        self.lbl_hk_status.setText("Жду нажатие… (клавиши или боковая кнопка мыши)")
        self.lbl_hk_status.setStyleSheet(f"color: {ACCENT}; font-weight: 700; font-size: 16px;")
        self.hotkeys.start_capture(lambda s: self.hotkey_captured.emit(s))

    def on_hotkey_captured(self, combo: str):
        self.cfg["hotkey"] = combo
        save_config(self.cfg)
        self.hotkeys.set_hotkey(combo)
        self.lbl_hk.setText(hotkey_label(combo))
        self.lbl_hk_status.setText(f"Сохранено: {hotkey_label(combo)}")
        self.lbl_hk_status.setStyleSheet(f"color: {OK}; font-weight: 700; font-size: 16px;")
        self.append_log(f"Хоткей назначен: {combo}")

    def reset_hotkey(self):
        self.on_hotkey_captured("ctrl+alt+q")

    def test_hotkey(self):
        self._hk_test_mode = True
        self.lbl_hk_status.setText("Тест: нажмите хоткей в течение 5 сек…")
        self.lbl_hk_status.setStyleSheet(f"color: {ACCENT}; font-weight: 700; font-size: 16px;")
        QTimer.singleShot(5000, self._test_hk_timeout)

    def _test_hk_timeout(self):
        if getattr(self, "_hk_test_mode", False):
            self._hk_test_mode = False
            self.lbl_hk_status.setText("Тест: не поймали нажатие. Проверьте назначение.")
            self.lbl_hk_status.setStyleSheet(f"color: {DANGER}; font-weight: 700; font-size: 16px;")

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
    app.setStyleSheet(THEME_QSS)
    icon_path = ASSETS / "radar.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    win = MainWindow()
    win.show()
    return app.exec()
