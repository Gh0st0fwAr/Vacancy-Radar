# -*- coding: utf-8 -*-
"""Replace _build_ui / save_opts / refresh / run in radar/ui.py."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
path = ROOT / "radar" / "ui.py"
text = path.read_text(encoding="utf-8")

# Russian UI strings as unicode escapes (ASCII source file).
S = {
    "search": "\u0418\u0441\u043a\u0430\u0442\u044c \u0441\u0435\u0439\u0447\u0430\u0441",
    "stats": "\u0421\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0430",
    "login": "\u0412\u043e\u0439\u0442\u0438 \u0432 HH / Chrome",
    "link": "\u0421\u0432\u044f\u0437\u044c",
    "letters": "\u041f\u0435\u0440\u0435\u0441\u043e\u0431\u0440\u0430\u0442\u044c \u043f\u0438\u0441\u044c\u043c\u0430",
    "new": "\u041d\u043e\u0432\u0430\u044f",
    "my_apply": "\u041c\u043e\u0439 \u043e\u0442\u043a\u043b\u0438\u043a",
    "employer": "\u041e\u0442\u0432\u0435\u0442 \u0440\u0430\u0431\u043e\u0442\u043e\u0434\u0430\u0442\u0435\u043b\u044f",
    "pointer": "\u0423\u043a\u0430\u0437\u0430\u0442\u0435\u043b\u044c",
    "theme": "\u0422\u0435\u043c\u0430:",
    "queue_title": "\u041e\u0447\u0435\u0440\u0435\u0434\u044c (\u226570%) \u2014 \u043d\u043e\u0432\u044b\u0435 \u0441\u0432\u0435\u0440\u0445\u0443",
    "open": "\u041e\u0442\u043a\u0440\u044b\u0442\u044c",
    "applied": "\u041e\u0442\u043a\u043b\u0438\u043a\u043d\u0443\u043b\u0441\u044f",
    "skip": "\u0421\u043a\u0438\u043f",
    "ban": "\u0423\u0434\u0430\u043b\u0438\u0442\u044c",
    "letter_title": "\u0421\u043e\u043f\u0440\u043e\u0432\u043e\u0434\u0438\u0442\u0435\u043b\u044c\u043d\u043e\u0435 (\u0431\u0443\u0444\u0435\u0440)",
    "copy": "\u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u043f\u0438\u0441\u044c\u043c\u043e",
    "card": "\u041a\u0430\u0440\u0442\u043e\u0447\u043a\u0430 \u0432\u0430\u043a\u0430\u043d\u0441\u0438\u0438",
    "hotkey": "\u0425\u043e\u0442\u043a\u0435\u0439",
    "assign": "\u041d\u0430\u0437\u043d\u0430\u0447\u0438\u0442\u044c",
    "check": "\u041f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c",
    "reset": "\u0421\u0431\u0440\u043e\u0441 Ctrl+Alt+Q",
    "opts": "\u041e\u043f\u0446\u0438\u0438",
    "sound": "\u0417\u0432\u0443\u043a (\u00d73) \u043f\u0440\u0438 \u043d\u043e\u0432\u043e\u0439 \u0432\u0430\u043a\u0430\u043d\u0441\u0438\u0438",
    "dnd": "DND \u2014 \u0431\u0435\u0437 \u0437\u0432\u0443\u043a\u0430",
    "min_prev": "\u0421\u0432\u043e\u0440\u0430\u0447\u0438\u0432\u0430\u0442\u044c \u043f\u0440\u0435\u0434\u044b\u0434\u0443\u0449\u0435\u0435 \u043e\u043a\u043d\u043e \u043f\u043e \u0445\u043e\u0442\u043a\u0435\u044e",
    "autostart": "\u0412\u043a\u043b\u044e\u0447\u0430\u0442\u044c \u043f\u0440\u0438 \u0437\u0430\u043f\u0443\u0441\u043a\u0435 \u0441\u0438\u0441\u0442\u0435\u043c\u044b",
    "guide_stats": "\u0413\u0430\u0439\u0434: \u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0430 HH",
    "guide_hk": "\u0413\u0430\u0439\u0434: \u0445\u043e\u0442\u043a\u0435\u0439",
    "log": "\u041b\u043e\u0433",
    "wait": "\u041e\u0436\u0438\u0434\u0430\u043d\u0438\u0435",
    "total": "\u0412\u0441\u0435\u0433\u043e",
    "inv": "\u041f\u0440\u0438\u0433\u043b\u0430\u0448.",
    "inter": "\u0421\u043e\u0431\u0435\u0441\u0435\u0434.",
    "ref": "\u041e\u0442\u043a\u0430\u0437\u044b",
    "chats": "\u0427\u0430\u0442\u044b",
    "views": "\u041f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u044b",
    "shows": "\u041f\u043e\u043a\u0430\u0437\u044b",
    "queue": "\u041e\u0447\u0435\u0440\u0435\u0434\u044c",
    "not_upd": "\u0435\u0449\u0451 \u043d\u0435 \u043e\u0431\u043d\u043e\u0432\u043b\u044f\u043b\u043e\u0441\u044c",
    "theme_log": "\u0422\u0435\u043c\u0430 UI:",
}

build_start = text.find("    def _build_ui(self):")
build_end = text.find("    def _build_tray(self):")
if build_start < 0 or build_end < 0:
    raise SystemExit("build markers missing")

new_build = f'''    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(12, 10, 12, 8)
        outer.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(10)
        self.btn_search = ScaleButton("{S['search']}", role="ok")
        self.btn_search.clicked.connect(self.run_search)
        self.btn_stats = ScaleButton("{S['stats']}")
        self.btn_stats.clicked.connect(self.run_stats)
        self.btn_login = ScaleButton("{S['login']}", role="primary")
        self.btn_login.clicked.connect(self.do_login_chrome)
        self.btn_check = ScaleButton("{S['link']}")
        self.btn_check.clicked.connect(self.do_check)
        self.btn_letters = ScaleButton("{S['letters']}", role="ghost")
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

        legend = QHBoxLayout()
        legend.setSpacing(8)
        for text_l, bg, fg, border in (
            ("{S['new']}", "transparent", "#f5f7fa", "#dfe6ee"),
            ("{S['my_apply']}", "#2a3038", "#9aa3ad", "#6b7280"),
            ("{S['employer']}", "#1e3348", "#7eb6f0", "#7eb6f0"),
            ("{S['pointer']}", "#1f5c32", "#8dff9a", "#3dff6a"),
        ):
            chip = QLabel(text_l)
            chip.setObjectName("legendChip")
            chip.setStyleSheet(
                f"QLabel#legendChip {{ background:{{bg}}; color:{{fg}}; "
                f"border: 3px solid {{border}}; }}"
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
        legend.addWidget(QLabel("{S['theme']}"))
        legend.addWidget(self.cmb_theme)
        outer.addLayout(legend)

        splitter = QSplitter()
        outer.addWidget(splitter, stretch=1)

        left = QWidget()
        left_l = QVBoxLayout(left)
        left_l.setContentsMargins(0, 0, 6, 0)
        left_l.setSpacing(10)
        q_title = QLabel("{S['queue_title']}")
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
        self.btn_open = ScaleButton("{S['open']}", role="primary")
        self.btn_open.clicked.connect(self.open_selected)
        self.btn_applied = ScaleButton("{S['applied']}", role="ok")
        self.btn_applied.clicked.connect(lambda: self.mark_selected("applied"))
        self.btn_skip = ScaleButton("{S['skip']}", role="warn")
        self.btn_skip.clicked.connect(lambda: self.mark_selected("skipped"))
        self.btn_ban = ScaleButton("{S['ban']}", role="danger")
        self.btn_ban.clicked.connect(lambda: self.mark_selected("banned"))
        for b in (self.btn_open, self.btn_applied, self.btn_skip, self.btn_ban):
            b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            btns.addWidget(b)
        left_l.addLayout(btns)
        splitter.addWidget(left)

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
        letter_title = QLabel("{S['letter_title']}")
        letter_title.setObjectName("sectionTitle")
        letter_row.addWidget(letter_title, stretch=1)
        self.btn_copy_letter = ScaleButton("{S['copy']}", role="primary")
        self.btn_copy_letter.clicked.connect(self.copy_selected_letter)
        letter_row.addWidget(self.btn_copy_letter)
        right_l.addLayout(letter_row)
        self.letter_view = QTextEdit()
        self.letter_view.setReadOnly(True)
        self.letter_view.setMinimumHeight(220)
        self.letter_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        right_l.addWidget(self.letter_view, stretch=2)

        card_title = QLabel("{S['card']}")
        card_title.setObjectName("sectionTitle")
        right_l.addWidget(card_title)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMinimumHeight(120)
        self.detail.setMaximumHeight(200)
        right_l.addWidget(self.detail)

        hk_box = QGroupBox("{S['hotkey']}")
        hk_l = QVBoxLayout(hk_box)
        self.lbl_hk_status = QLabel("")
        self.lbl_hk_status.setObjectName("mutedLabel")
        self.lbl_hk_status.setWordWrap(True)
        hk_l.addWidget(self.lbl_hk_status)
        hk_btns = QHBoxLayout()
        self.btn_set_hk = ScaleButton("{S['assign']}", role="primary")
        self.btn_set_hk.clicked.connect(self.capture_hotkey)
        self.btn_test_hk = ScaleButton("{S['check']}")
        self.btn_test_hk.clicked.connect(self.test_hotkey)
        self.btn_reset_hk = ScaleButton("{S['reset']}", role="ghost")
        self.btn_reset_hk.clicked.connect(self.reset_hotkey)
        for b in (self.btn_set_hk, self.btn_test_hk, self.btn_reset_hk):
            hk_btns.addWidget(b)
        hk_l.addLayout(hk_btns)
        right_l.addWidget(hk_box)

        opt = QGroupBox("{S['opts']}")
        ol = QVBoxLayout(opt)
        self.chk_sound = QCheckBox("{S['sound']}")
        self.chk_sound.setChecked(bool(self.cfg.get("sound_enabled", True)))
        self.chk_sound.stateChanged.connect(self.save_opts)
        self.chk_dnd = QCheckBox("{S['dnd']}")
        self.chk_dnd.setChecked(bool(self.cfg.get("dnd", False)))
        self.chk_dnd.stateChanged.connect(self.save_opts)
        self.chk_min = QCheckBox("{S['min_prev']}")
        self.chk_min.setChecked(bool(self.cfg.get("minimize_previous", False)))
        self.chk_min.stateChanged.connect(self.save_opts)
        self.chk_autostart = QCheckBox("{S['autostart']}")
        self.chk_autostart.setChecked(
            bool(self.cfg.get("autostart_enabled", False)) or is_autostart_enabled()
        )
        self.chk_autostart.stateChanged.connect(self.save_opts)
        for chk in (self.chk_sound, self.chk_dnd, self.chk_min, self.chk_autostart):
            chk.setMinimumHeight(36)
            ol.addWidget(chk)
        right_l.addWidget(opt)

        guide_row = QHBoxLayout()
        self.btn_guide = ScaleButton("{S['guide_stats']}", role="ghost")
        self.btn_guide.clicked.connect(lambda: self.show_text("{S['guide_stats']}", GUIDE_STATS))
        self.btn_guide_hk = ScaleButton("{S['guide_hk']}", role="ghost")
        self.btn_guide_hk.clicked.connect(lambda: self.show_text("{S['guide_hk']}", GUIDE_HOTKEY))
        guide_row.addWidget(self.btn_guide)
        guide_row.addWidget(self.btn_guide_hk)
        right_l.addLayout(guide_row)

        log_title = QLabel("{S['log']}")
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

        stats_frame = QFrame()
        stats_frame.setObjectName("statsStrip")
        stats_frame.setStyleSheet(
            "QFrame#statsStrip {{ background-color: #252b33; border: 1px solid #3a4450; "
            "border-radius: 10px; padding: 4px; }}"
        )
        sf = QHBoxLayout(stats_frame)
        sf.setSpacing(14)
        self.lbl_active = QLabel("\\u2014")
        self.lbl_total = QLabel("\\u2014")
        self.lbl_inv = QLabel("\\u2014")
        self.lbl_interviews = QLabel("\\u2014")
        self.lbl_refusals = QLabel("\\u2014")
        self.lbl_unread = QLabel("\\u2014")
        self.lbl_views = QLabel("\\u2014")
        self.lbl_shows = QLabel("\\u2014")
        self.lbl_queue = QLabel("0")
        self.lbl_stats_at = QLabel("{S['not_upd']}")
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

        _pair("{S['wait']}", self.lbl_active)
        _pair("{S['total']}", self.lbl_total)
        _pair("{S['inv']}", self.lbl_inv)
        _pair("{S['inter']}", self.lbl_interviews)
        _pair("{S['ref']}", self.lbl_refusals)
        _pair("{S['chats']}", self.lbl_unread)
        _pair("{S['views']}", self.lbl_views)
        _pair("{S['shows']}", self.lbl_shows)
        _pair("{S['queue']}", self.lbl_queue)
        sf.addStretch(1)
        right_meta = QVBoxLayout()
        right_meta.addWidget(self.lbl_stats_at)
        right_meta.addWidget(self.lbl_stats_note)
        sf.addLayout(right_meta)
        outer.addWidget(stats_frame)

'''

# Fix em-dash labels - use actual character
new_build = new_build.replace('"\\u2014"', '"\u2014"')

text = text[:build_start] + new_build + text[build_end:]

old_save = '''    def save_opts(self):
        self.cfg["sound_enabled"] = self.chk_sound.isChecked()
        self.cfg["dnd"] = self.chk_dnd.isChecked()
        self.cfg["minimize_previous"] = self.chk_min.isChecked()
        save_config(self.cfg)
'''

new_save = f'''    def save_opts(self):
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
        self.append_log(f"{S['theme_log']} {{THEME_LABELS.get(str(tid), tid)}}")
'''
if old_save not in text:
    raise SystemExit("save_opts missing")
text = text.replace(old_save, new_save, 1)

# Find refresh_queue_list and replace until on_select
r_start = text.find("    def refresh_queue_list(self):")
r_end = text.find("    def on_select(self, row: int):")
if r_start < 0 or r_end < 0:
    raise SystemExit("refresh markers missing")

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
                label = f"{badge}{v.score}%  {v.title}  \\u00b7  {v.company}"
            else:
                label = f"{badge}{v.title}  \\u00b7  {v.company}"
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
            if kind == "skipped" and not str(item.text()).startswith("\\u23ed "):
                item.setText("\\u23ed " + item.text())
            if is_active:
                t = item.text()
                if t.startswith("\\u23ed "):
                    t = t[2:]
                if not t.startswith("\\u2192 "):
                    item.setText("\\u2192 " + t)
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
# Convert escape sequences in new_refresh to real chars for the file
new_refresh = (
    new_refresh.replace("\\u00b7", "\u00b7")
    .replace("\\u23ed ", "\u23ed ")
    .replace("\\u2192 ", "\u2192 ")
)
text = text[:r_start] + new_refresh + text[r_end:]

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
    # maybe already patched
    if "apply_theme(app, str(cfg0.get" not in text:
        raise SystemExit("run() missing")
else:
    text = text.replace(old_run, new_run, 1)

path.write_text(text, encoding="utf-8")
compile(text, str(path), "exec")
print("part2 ok", path.stat().st_size)
