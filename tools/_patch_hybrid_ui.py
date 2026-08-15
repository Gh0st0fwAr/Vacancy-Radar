# -*- coding: utf-8 -*-
"""One-shot patch: hybrid UI layout + status delegate in radar/ui.py."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
path = ROOT / "radar" / "ui.py"
text = path.read_text(encoding="utf-8")

old_imp = """from PySide6.QtWidgets import (
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
)"""

new_imp = """from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
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
)"""
if old_imp not in text:
    raise SystemExit("imports block missing")
text = text.replace(old_imp, new_imp, 1)

start = text.find("from radar.queue_style import")
end = text.find("\ndef log(")
if start < 0 or end < 0:
    raise SystemExit(f"marker fail start={start} end={end}")

new_mid = r'''from radar.autostart import is_autostart_enabled, set_autostart
from radar.queue_style import (
    ICON_SIZE,
    STATUS_KIND_ROLE,
    colors_for_kind,
    icon_for,
    is_blue,
    is_gray_apply,
    is_white,
    status_kind,
)
from radar.stats_hh import fetch_stats
from radar.theme import (
    ACCENT,
    DANGER,
    OK,
    ScaleButton,
    TEXT_DIM,
    THEME_LABELS,
    WARN,
    apply_app_font,
    apply_theme,
    current_theme_id,
)
from radar.themes import THEME_IDS

# ?????? «???????? ?????????» (?????? / ????????? ????????).
ACTIVE_ROLE = Qt.UserRole + 1
HH_HIGHLIGHT_ROLE = Qt.UserRole + 2
STRIPE_W = 10


class StatusListDelegate(QStyledItemDelegate):
    """??????? ????? + ??? ?????? + ???? ????????? + ??????."""

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        rect = option.rect.adjusted(2, 1, -2, -1)
        kind = index.data(STATUS_KIND_ROLE) or "other"
        fg, bg, stripe = colors_for_kind(str(kind))

        if bg.alpha() > 0:
            painter.fillRect(rect, bg)
        elif option.state & QStyle.State_Selected:
            painter.fillRect(rect, QColor(ACCENT).darker(220))
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(rect, QColor(60, 70, 80, 80))

        if option.state & QStyle.State_Selected:
            painter.setPen(QColor(ACCENT))
            painter.drawRoundedRect(rect.adjusted(0, 0, -1, -1), 8, 8)

        stripe_rect = rect.adjusted(0, 2, 0, -2)
        stripe_rect.setWidth(STRIPE_W)
        painter.fillRect(stripe_rect, stripe)

        icon = index.data(Qt.DecorationRole)
        x = rect.left() + STRIPE_W + 10
        y = rect.top()
        h = rect.height()
        if isinstance(icon, QIcon) and not icon.isNull():
            sz = ICON_SIZE
            iy = y + max(0, (h - sz.height()) // 2)
            icon.paint(painter, x, iy, sz.width(), sz.height())
            x += sz.width() + 10
        else:
            x += 4

        text_s = index.data(Qt.DisplayRole) or ""
        font = QFont(option.font)
        item_font = index.data(Qt.FontRole)
        if isinstance(item_font, QFont):
            font = QFont(item_font)
        painter.setFont(font)
        painter.setPen(fg if fg.isValid() else QColor("#e8edf2"))
        text_rect = rect.adjusted(x - rect.left(), 4, -10, -4)
        flags = int(Qt.AlignVCenter | Qt.AlignLeft | Qt.TextWordWrap)
        painter.drawText(text_rect, flags, text_s)
        painter.restore()

    def sizeHint(self, option, index):
        sh = super().sizeHint(option, index)
        sh.setHeight(max(sh.height(), 64))
        return sh


'''

text = text[:start] + new_mid + text[end + 1 :]  # keep leading \n before def log

# Replace PointerGlowDelegate reference
text = text.replace("PointerGlowDelegate(self.list)", "StatusListDelegate(self.list)")

# Replace entire _build_ui method
build_start = text.find("    def _build_ui(self):")
build_end = text.find("    def _build_tray(self):")
if build_start < 0 or build_end < 0:
    raise SystemExit("build_ui markers missing")

new_build = r'''    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(12, 10, 12, 8)
        outer.setSpacing(10)

        # --- Top toolbar (hybrid) ---
        top = QHBoxLayout()
        top.setSpacing(10)
        self.btn_search = ScaleButton("?????? ??????", role="ok")
        self.btn_search.clicked.connect(self.run_search)
        self.btn_stats = ScaleButton("??????????")
        self.btn_stats.clicked.connect(self.run_stats)
        self.btn_login = ScaleButton("????? ? HH / Chrome", role="primary")
        self.btn_login.clicked.connect(self.do_login_chrome)
        self.btn_check = ScaleButton("?????")
        self.btn_check.clicked.connect(self.do_check)
        self.btn_letters = ScaleButton("??????????? ??????", role="ghost")
        self.btn_letters.clicked.connect(self.rebuild_letters)
        for b in (
            self.btn_search,
            self.btn_stats,
            self.btn_login,
            self.btn_check,
            self.btn_letters,
        ):
            b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            top.addWidget(b)
        top.addStretch(1)
        self.lbl_hk = QLabel(hotkey_label(self.cfg.get("hotkey") or "ctrl+alt+q"))
        self.lbl_hk.setObjectName("hotkeyBadge")
        self.lbl_hk.setAlignment(Qt.AlignCenter)
        self.lbl_hk.setMinimumHeight(48)
        top.addWidget(self.lbl_hk)
        outer.addLayout(top)

        # Legend
        legend = QHBoxLayout()
        legend.setSpacing(8)
        for text_l, bg, fg, border in (
            ("?????", "transparent", "#f5f7fa", "#dfe6ee"),
            ("??? ??????", "#2a3038", "#9aa3ad", "#6b7280"),
            ("????? ????????????", "#1e3348", "#7eb6f0", "#7eb6f0"),
            ("?????????", "#1f5c32", "#8dff9a", "#3dff6a"),
        ):
            chip = QLabel(text_l)
            chip.setObjectName("legendChip")
            chip.setStyleSheet(
                f"QLabel#legendChip {{ background:{bg}; color:{fg}; "
                f"border: 3px solid {border}; }}"
            )
            legend.addWidget(chip)
        legend.addStretch(1)
        self.cmb_theme = QComboBox()
        for tid in THEME_IDS:
            self.cmb_theme.addItem(THEME_LABELS.get(tid, tid), tid)
        cur = str(self.cfg.get("ui_theme") or "04")
        idx = max(0, self.cmb_theme.findData(cur))
        self.cmb_theme.setCurrentIndex(idx)
        self.cmb_theme.currentIndexChanged.connect(self.on_theme_changed)
        legend.addWidget(QLabel("????:"))
        legend.addWidget(self.cmb_theme)
        outer.addLayout(legend)

        splitter = QSplitter()
        outer.addWidget(splitter, stretch=1)

        # Left: queue
        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 6, 0)
        left_l.setSpacing(10)
        q_title = QLabel("??????? (?70%) — ????? ??????")
        q_title.setObjectName("sectionTitle")
        left_l.addWidget(q_title)
        self.list = QListWidget()
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.setTextElideMode(Qt.ElideRight)
        self.list.setWordWrap(True)
        self.list.setMinimumHeight(160)
        self.list.setIconSize(ICON_SIZE)
        self.list.setSpacing(6)
        self.list.setItemDelegate(StatusListDelegate(self.list))
        self.list.currentRowChanged.connect(self.on_select)
        left_l.addWidget(self.list, stretch=1)

        btns = QHBoxLayout()
        btns.setSpacing(10)
        self.btn_open = ScaleButton("???????", role="primary")
        self.btn_open.clicked.connect(self.open_selected)
        self.btn_applied = ScaleButton("???????????", role="ok")
        self.btn_applied.clicked.connect(lambda: self.mark_selected("applied"))
        self.btn_skip = ScaleButton("????", role="warn")
        self.btn_skip.clicked.connect(lambda: self.mark_selected("skipped"))
        self.btn_ban = ScaleButton("???????", role="danger")
        self.btn_ban.clicked.connect(lambda: self.mark_selected("banned"))
        for b in (self.btn_open, self.btn_applied, self.btn_skip, self.btn_ban):
            b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            btns.addWidget(b)
        left_l.addLayout(btns)
        splitter.addWidget(left)

        # Right: letter + detail + options
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QScrollArea.NoFrame)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        right = QWidget()
        right.setMinimumWidth(440)
        right_l = QVBoxLayout(right)
        right_l.setContentsMargins(6, 0, 4, 0)
        right_l.setSpacing(12)
        right_l.setAlignment(Qt.AlignTop)

        letter_row = QHBoxLayout()
        letter_title = QLabel("???????????????? (?????)")
        letter_title.setObjectName("sectionTitle")
        letter_row.addWidget(letter_title, stretch=1)
        self.btn_copy_letter = ScaleButton("??????????? ??????", role="primary")
        self.btn_copy_letter.clicked.connect(self.copy_selected_letter)
        letter_row.addWidget(self.btn_copy_letter)
        right_l.addLayout(letter_row)
        self.letter_view = QTextEdit()
        self.letter_view.setReadOnly(True)
        self.letter_view.setMinimumHeight(220)
        self.letter_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_l.addWidget(self.letter_view, stretch=2)

        card_title = QLabel("???????? ????????")
        card_title.setObjectName("sectionTitle")
        right_l.addWidget(card_title)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMinimumHeight(120)
        self.detail.setMaximumHeight(200)
        right_l.addWidget(self.detail)

        hk_box = QGroupBox("??????")
        hk_l = QVBoxLayout(hk_box)
        self.lbl_hk_status = QLabel("")
        self.lbl_hk_status.setObjectName("mutedLabel")
        self.lbl_hk_status.setWordWrap(True)
        hk_l.addWidget(self.lbl_hk_status)
        hk_btns = QHBoxLayout()
        self.btn_set_hk = ScaleButton("?????????", role="primary")
        self.btn_set_hk.clicked.connect(self.capture_hotkey)
        self.btn_test_hk = ScaleButton("?????????")
        self.btn_test_hk.clicked.connect(self.test_hotkey)
        self.btn_reset_hk = ScaleButton("????? Ctrl+Alt+Q", role="ghost")
        self.btn_reset_hk.clicked.connect(self.reset_hotkey)
        for b in (self.btn_set_hk, self.btn_test_hk, self.btn_reset_hk):
            hk_btns.addWidget(b)
        hk_l.addLayout(hk_btns)
        right_l.addWidget(hk_box)

        opt = QGroupBox("?????")
        ol = QVBoxLayout(opt)
        self.chk_sound = QCheckBox("???? (×3) ??? ????? ????????")
        self.chk_sound.setChecked(bool(self.cfg.get("sound_enabled", True)))
        self.chk_sound.stateChanged.connect(self.save_opts)
        self.chk_dnd = QCheckBox("DND — ??? ?????")
        self.chk_dnd.setChecked(bool(self.cfg.get("dnd", False)))
        self.chk_dnd.stateChanged.connect(self.save_opts)
        self.chk_min = QCheckBox("??????????? ?????????? ???? ?? ??????")
        self.chk_min.setChecked(bool(self.cfg.get("minimize_previous", False)))
        self.chk_min.stateChanged.connect(self.save_opts)
        self.chk_autostart = QCheckBox("???????? ??? ??????? ???????")
        self.chk_autostart.setChecked(
            bool(self.cfg.get("autostart_enabled", False)) or is_autostart_enabled()
        )
        self.chk_autostart.stateChanged.connect(self.save_opts)
        for chk in (self.chk_sound, self.chk_dnd, self.chk_min, self.chk_autostart):
            chk.setMinimumHeight(36)
            ol.addWidget(chk)
        right_l.addWidget(opt)

        guide_row = QHBoxLayout()
        self.btn_guide = ScaleButton("????: ?????????? HH", role="ghost")
        self.btn_guide.clicked.connect(lambda: self.show_text("????: ?????????? HH", GUIDE_STATS))
        self.btn_guide_hk = ScaleButton("????: ??????", role="ghost")
        self.btn_guide_hk.clicked.connect(lambda: self.show_text("????: ??????", GUIDE_HOTKEY))
        guide_row.addWidget(self.btn_guide)
        guide_row.addWidget(self.btn_guide_hk)
        right_l.addLayout(guide_row)

        log_title = QLabel("???")
        log_title.setObjectName("sectionTitle")
        right_l.addWidget(log_title)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(100)
        self.log_view.setMaximumHeight(180)
        right_l.addWidget(self.log_view)
        right_l.addStretch(1)

        right_scroll.setWidget(right)
        splitter.addWidget(right_scroll)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setChildrenCollapsible(False)

        # Bottom stats strip
        stats_frame = QFrame()
        stats_frame.setObjectName("statsStrip")
        stats_frame.setStyleSheet(
            "QFrame#statsStrip { background-color: #252b33; border: 1px solid #3a4450; "
            "border-radius: 10px; padding: 4px; }"
        )
        sf = QHBoxLayout(stats_frame)
        sf.setSpacing(14)
        self.lbl_active = QLabel("—")
        self.lbl_total = QLabel("—")
        self.lbl_inv = QLabel("—")
        self.lbl_interviews = QLabel("—")
        self.lbl_refusals = QLabel("—")
        self.lbl_unread = QLabel("—")
        self.lbl_views = QLabel("—")
        self.lbl_shows = QLabel("—")
        self.lbl_queue = QLabel("0")
        self.lbl_stats_at = QLabel("??? ?? ???????????")
        self.lbl_stats_note = QLabel("")
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
        self.lbl_stats_note.setObjectName("mutedLabel")

        def _pair(title: str, val: QLabel):
            w = QWidget()
            vl = QVBoxLayout(w)
            vl.setContentsMargins(0, 0, 0, 0)
            vl.setSpacing(2)
            t = QLabel(title)
            t.setObjectName("mutedLabel")
            vl.addWidget(t)
            vl.addWidget(val)
            sf.addWidget(w)

        _pair("????????", self.lbl_active)
        _pair("?????", self.lbl_total)
        _pair("???????.", self.lbl_inv)
        _pair("???????.", self.lbl_interviews)
        _pair("??????", self.lbl_refusals)
        _pair("????", self.lbl_unread)
        _pair("?????????", self.lbl_views)
        _pair("??????", self.lbl_shows)
        _pair("???????", self.lbl_queue)
        sf.addStretch(1)
        right_meta = QVBoxLayout()
        right_meta.addWidget(self.lbl_stats_at)
        right_meta.addWidget(self.lbl_stats_note)
        sf.addLayout(right_meta)
        outer.addWidget(stats_frame)

'''

text = text[:build_start] + new_build + text[build_end:]

# save_opts
old_save = '''    def save_opts(self):
        self.cfg["sound_enabled"] = self.chk_sound.isChecked()
        self.cfg["dnd"] = self.chk_dnd.isChecked()
        self.cfg["minimize_previous"] = self.chk_min.isChecked()
        save_config(self.cfg)
'''

new_save = '''    def save_opts(self):
        self.cfg["sound_enabled"] = self.chk_sound.isChecked()
        self.cfg["dnd"] = self.chk_dnd.isChecked()
        self.cfg["minimize_previous"] = self.chk_min.isChecked()
        want_auto = self.chk_autostart.isChecked()
        self.cfg["autostart_enabled"] = want_auto
        msg = set_autostart(want_auto)
        save_config(self.cfg)
        self.append_log(msg)

    def on_theme_changed(self, _index: int = 0):
        tid = self.cmb_theme.currentData()
        if not tid:
            return
        self.cfg["ui_theme"] = str(tid)
        save_config(self.cfg)
        app = QApplication.instance()
        apply_theme(app, str(tid))
        self.refresh_queue_list()
        self.append_log(f"???? UI: {THEME_LABELS.get(str(tid), tid)}")
'''
if old_save not in text:
    raise SystemExit("save_opts missing")
text = text.replace(old_save, new_save, 1)

# refresh_queue_list body — replace color block
old_refresh = '''    def refresh_queue_list(self):
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
            # ?????: ????? ????? ???????????? ? ????? ??? ?????? ? ????? ????? ? …
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
                item.setText("? " + item.text())
            # ??????? ?????? ? ????????? ????????? (?????? ????????? ?????? ??????).
            if is_active:
                f = item.font()
                f.setBold(True)
                f.setPointSize(max(f.pointSize(), 16))
                item.setFont(f)
                item.setForeground(POINTER_GREEN)
                t = item.text()
                if t.startswith("? "):
                    t = t[2:]
                if not t.startswith("? "):
                    item.setText("? " + t)
            self.list.addItem(item)
        self.lbl_queue.setText(str(new_count))
        # ????????? ?????????: ??????? ???????? ?????????, ????? ??????? ?????.
        restore = active or prev
        if restore:
            self._select_url(restore)
'''

new_refresh = '''    def refresh_queue_list(self):
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
            kind = status_kind(v, is_active=is_active)
            item.setData(STATUS_KIND_ROLE, kind)
            if kind == "new":
                new_count += 1
            if kind == "skipped" and not label.startswith("? "):
                item.setText("? " + label)
            if is_active:
                t = item.text()
                if t.startswith("? "):
                    t = t[2:]
                if not t.startswith("? "):
                    item.setText("? " + t)
            ic = icon_for(v)
            if not ic.isNull():
                item.setIcon(ic)
            fg, _bg, _stripe = colors_for_kind(kind)
            item.setForeground(fg)
            f = item.font()
            f.setBold(kind in ("new", "invite", "pointer"))
            f.setPointSize(max(f.pointSize(), 16 if kind == "pointer" else 14))
            item.setFont(f)
            self.list.addItem(item)
        self.lbl_queue.setText(str(new_count))
        restore = active or prev
        if restore:
            self._select_url(restore)
'''
if old_refresh not in text:
    raise SystemExit("refresh_queue_list missing")
text = text.replace(old_refresh, new_refresh, 1)

# run()
old_run = '''def run():
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
'''

new_run = '''def run():
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
    win.show()
    return app.exec()
'''
if old_run not in text:
    raise SystemExit("run() missing")
text = text.replace(old_run, new_run, 1)

# After __init__ apply theme from cfg (window already has stylesheet from app)
# Ensure MainWindow __init__ syncs theme id — optional.

path.write_text(text, encoding="utf-8")
print("patched", path, "bytes", path.stat().st_size)
# sanity
compile(text, str(path), "exec")
print("syntax OK")
