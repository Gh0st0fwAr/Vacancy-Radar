# -*- coding: utf-8 -*-
"""Reference-04 shell layout for VacancyRadar MainWindow."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from radar.config import ASSETS
from radar.guides import GUIDE_HOTKEY, GUIDE_STATS
from radar.hotkeys import hotkey_label
from radar.autostart import is_autostart_enabled
from radar.queue_style import ICON_SIZE
from radar.theme import ScaleButton, THEME_LABELS
from radar.themes import THEME_IDS
from radar.vacancy_delegate import VacancyCardDelegate


def _icon(name: str) -> QIcon:
    p = ASSETS / name
    if not p.exists():
        return QIcon()
    return QIcon(QPixmap(str(p)))


def _nav_btn(text: str, icon_name: str) -> QToolButton:
    b = QToolButton()
    b.setText(text)
    b.setIcon(_icon(icon_name))
    b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
    b.setCheckable(True)
    b.setAutoExclusive(True)
    b.setObjectName("navBtn")
    b.setCursor(Qt.PointingHandCursor)
    b.setMinimumWidth(72)
    b.setMinimumHeight(56)
    return b


def _metric(icon_name: str, caption: str) -> tuple[QWidget, QLabel]:
    w = QWidget()
    lay = QHBoxLayout(w)
    lay.setContentsMargins(4, 2, 10, 2)
    lay.setSpacing(8)
    ic = QLabel()
    pix = QPixmap(str(ASSETS / icon_name)) if (ASSETS / icon_name).exists() else QPixmap()
    if not pix.isNull():
        ic.setPixmap(pix.scaled(22, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    lay.addWidget(ic)
    col = QVBoxLayout()
    col.setSpacing(0)
    cap = QLabel(caption)
    cap.setObjectName("mutedLabel")
    val = QLabel("\u2014")
    val.setObjectName("statsValue")
    col.addWidget(cap)
    col.addWidget(val)
    lay.addLayout(col)
    return w, val


def attach_shell(win) -> None:
    """Build reference-04 chrome and bind widgets onto MainWindow `win`."""
    root = QWidget()
    win.setCentralWidget(root)
    outer = QVBoxLayout(root)
    outer.setContentsMargins(14, 12, 14, 10)
    outer.setSpacing(12)

    # ----- Top toolbar -----
    top = QHBoxLayout()
    top.setSpacing(12)

    win.btn_search = ScaleButton("  \u0418\u0441\u043a\u0430\u0442\u044c \u0441\u0435\u0439\u0447\u0430\u0441   F5", role="primary")
    win.btn_search.setIcon(_icon("tb_search.png"))
    win.btn_search.setIconSize(ICON_SIZE)
    win.btn_search.clicked.connect(win.run_search)

    win.btn_stats = ScaleButton("  \u041e\u0431\u043d\u043e\u0432\u0438\u0442\u044c \u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0443   F9", role="ghost")
    win.btn_stats.setIcon(_icon("tb_refresh.png"))
    win.btn_stats.setIconSize(ICON_SIZE)
    win.btn_stats.clicked.connect(win.run_stats)

    for b in (win.btn_search, win.btn_stats):
        b.setMinimumHeight(44)
        b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        top.addWidget(b)

    top.addStretch(1)
    win.lbl_hk = QLabel(hotkey_label(win.cfg.get("hotkey") or "ctrl+alt+q"))
    win.lbl_hk.setObjectName("hotkeyBadge")
    win.lbl_hk.setAlignment(Qt.AlignCenter)
    win.lbl_hk.setMinimumHeight(44)
    win.lbl_hk.setMinimumWidth(180)
    top.addWidget(win.lbl_hk)
    top.addStretch(1)

    win.nav_queue = _nav_btn("\u041e\u0447\u0435\u0440\u0435\u0434\u044c", "tb_queue.png")
    win.nav_stats = _nav_btn("\u0421\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0430", "tb_stats.png")
    win.nav_settings = _nav_btn("\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438", "tb_settings.png")
    win.nav_queue.setChecked(True)
    win.nav_queue.clicked.connect(lambda: win.show_page(0))
    win.nav_stats.clicked.connect(lambda: win.show_page(1))
    win.nav_settings.clicked.connect(lambda: win.show_page(2))
    for b in (win.nav_queue, win.nav_stats, win.nav_settings):
        top.addWidget(b)
    outer.addLayout(top)

    # ----- Pages -----
    win.pages = QStackedWidget()
    outer.addWidget(win.pages, stretch=1)

    # === PAGE 0: Queue ===
    page_q = QWidget()
    pq = QHBoxLayout(page_q)
    pq.setContentsMargins(0, 0, 0, 0)
    pq.setSpacing(10)
    splitter = QSplitter()
    pq.addWidget(splitter)

    left = QWidget()
    left_l = QVBoxLayout(left)
    left_l.setContentsMargins(0, 0, 4, 0)
    left_l.setSpacing(8)

    head = QHBoxLayout()
    win.lbl_vac_count = QLabel("\u0412\u0430\u043a\u0430\u043d\u0441\u0438\u0438 (0)")
    win.lbl_vac_count.setObjectName("sectionTitle")
    head.addWidget(win.lbl_vac_count, stretch=1)
    lbl_st = QLabel("\u0421\u0442\u0430\u0442\u0443\u0441")
    lbl_st.setObjectName("mutedLabel")
    lbl_sc = QLabel("Score")
    lbl_sc.setObjectName("mutedLabel")
    head.addWidget(lbl_st)
    head.addSpacing(48)
    head.addWidget(lbl_sc)
    left_l.addLayout(head)

    win.list = QListWidget()
    win.list.setObjectName("vacancyList")
    win.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    win.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
    win.list.setSpacing(2)
    win.list.setIconSize(ICON_SIZE)
    win.list.setUniformItemSizes(True)
    win.list.setItemDelegate(VacancyCardDelegate(win.list))
    win.list.currentRowChanged.connect(win.on_select)
    left_l.addWidget(win.list, stretch=1)

    act = QHBoxLayout()
    act.setSpacing(8)
    win.btn_open = ScaleButton("\u041e\u0442\u043a\u0440\u044b\u0442\u044c", role="primary")
    win.btn_open.clicked.connect(win.open_selected)
    win.btn_applied = ScaleButton("\u041e\u0442\u043a\u043b\u0438\u043a\u043d\u0443\u043b\u0441\u044f", role="ok")
    win.btn_applied.clicked.connect(lambda: win.mark_selected("applied"))
    win.btn_skip = ScaleButton("\u0421\u043a\u0438\u043f", role="warn")
    win.btn_skip.clicked.connect(lambda: win.mark_selected("skipped"))
    win.btn_ban = ScaleButton("\u0423\u0434\u0430\u043b\u0438\u0442\u044c", role="danger")
    win.btn_ban.clicked.connect(lambda: win.mark_selected("banned"))
    for b in (win.btn_open, win.btn_applied, win.btn_skip, win.btn_ban):
        act.addWidget(b)
    left_l.addLayout(act)
    splitter.addWidget(left)

    # Right detail
    right = QWidget()
    right.setMinimumWidth(460)
    rl = QVBoxLayout(right)
    rl.setContentsMargins(4, 0, 0, 0)
    rl.setSpacing(10)

    hdr = QHBoxLayout()
    title_col = QVBoxLayout()
    win.lbl_detail_title = QLabel("\u2014")
    win.lbl_detail_title.setObjectName("detailTitle")
    win.lbl_detail_title.setWordWrap(True)
    win.lbl_detail_company = QLabel("")
    win.lbl_detail_company.setObjectName("detailCompany")
    win.lbl_detail_meta = QLabel("")
    win.lbl_detail_meta.setObjectName("mutedLabel")
    win.lbl_detail_meta.setWordWrap(True)
    title_col.addWidget(win.lbl_detail_title)
    title_col.addWidget(win.lbl_detail_company)
    title_col.addWidget(win.lbl_detail_meta)
    hdr.addLayout(title_col, stretch=1)

    score_col = QVBoxLayout()
    score_col.setAlignment(Qt.AlignRight | Qt.AlignTop)
    sc_cap = QLabel("Match Score")
    sc_cap.setObjectName("mutedLabel")
    sc_cap.setAlignment(Qt.AlignRight)
    win.lbl_detail_score = QLabel("\u2014")
    win.lbl_detail_score.setObjectName("detailScore")
    win.lbl_detail_score.setAlignment(Qt.AlignRight)
    win.btn_view_hh = ScaleButton("  \u041e\u0442\u043a\u0440\u044b\u0442\u044c \u043d\u0430 HH", role="ghost")
    win.btn_view_hh.setIcon(_icon("tb_external.png"))
    win.btn_view_hh.clicked.connect(win.open_selected)
    score_col.addWidget(sc_cap)
    score_col.addWidget(win.lbl_detail_score)
    score_col.addWidget(win.btn_view_hh)
    hdr.addLayout(score_col)
    rl.addLayout(hdr)

    # Two columns: details + letter (no extra tabs)
    cols = QHBoxLayout()
    cols.setSpacing(12)

    det_card = QFrame()
    det_card.setObjectName("panelCard")
    det_l = QVBoxLayout(det_card)
    det_h = QLabel("Details")
    det_h.setObjectName("sectionTitle")
    det_l.addWidget(det_h)
    win.detail = QTextEdit()
    win.detail.setReadOnly(True)
    win.detail.setObjectName("detailBody")
    det_l.addWidget(win.detail)
    cols.addWidget(det_card, stretch=2)

    let_card = QFrame()
    let_card.setObjectName("panelCard")
    let_l = QVBoxLayout(let_card)
    let_head = QHBoxLayout()
    let_h = QLabel("Cover Letter")
    let_h.setObjectName("sectionTitle")
    let_head.addWidget(let_h, stretch=1)
    win.btn_copy_letter = ScaleButton("  \u0421\u043a\u043e\u043f\u0438\u0440\u043e\u0432\u0430\u0442\u044c", role="primary")
    win.btn_copy_letter.setIcon(_icon("tb_copy.png"))
    win.btn_copy_letter.clicked.connect(win.copy_selected_letter)
    let_head.addWidget(win.btn_copy_letter)
    let_l.addLayout(let_head)
    win.letter_view = QTextEdit()
    win.letter_view.setReadOnly(True)
    let_l.addWidget(win.letter_view)
    cols.addWidget(let_card, stretch=3)

    rl.addLayout(cols, stretch=1)
    splitter.addWidget(right)
    splitter.setStretchFactor(0, 5)
    splitter.setStretchFactor(1, 6)
    splitter.setChildrenCollapsible(False)
    win.pages.addWidget(page_q)

    # === PAGE 1: Stats ===
    page_s = QScrollArea()
    page_s.setWidgetResizable(True)
    page_s.setFrameShape(QScrollArea.NoFrame)
    sw = QWidget()
    sl = QVBoxLayout(sw)
    sl.setSpacing(14)
    st_title = QLabel("\u0421\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0430 HH")
    st_title.setObjectName("sectionTitle")
    sl.addWidget(st_title)

    row = QHBoxLayout()
    win.btn_login = ScaleButton("\u0412\u043e\u0439\u0442\u0438 \u0432 HH / Chrome", role="primary")
    win.btn_login.clicked.connect(win.do_login_chrome)
    win.btn_check = ScaleButton("\u041f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c \u0441\u0432\u044f\u0437\u044c")
    win.btn_check.clicked.connect(win.do_check)
    win.btn_letters = ScaleButton("\u041f\u0435\u0440\u0435\u0441\u043e\u0431\u0440\u0430\u0442\u044c \u043f\u0438\u0441\u044c\u043c\u0430", role="ghost")
    win.btn_letters.clicked.connect(win.rebuild_letters)
    for b in (win.btn_login, win.btn_check, win.btn_letters, win.btn_stats):
        # btn_stats already in top; clone refresh on this page via same handler
        pass
    for b in (win.btn_login, win.btn_check, win.btn_letters):
        row.addWidget(b)
    row.addStretch(1)
    sl.addLayout(row)

    stats_box = QGroupBox("Frontend-\u0440\u0435\u0437\u044e\u043c\u0435")
    from PySide6.QtWidgets import QFormLayout

    sf = QFormLayout(stats_box)
    win.lbl_active = QLabel("\u2014")
    win.lbl_total = QLabel("\u2014")
    win.lbl_inv = QLabel("\u2014")
    win.lbl_interviews = QLabel("\u2014")
    win.lbl_refusals = QLabel("\u2014")
    win.lbl_unread = QLabel("\u2014")
    win.lbl_views = QLabel("\u2014")
    win.lbl_shows = QLabel("\u2014")
    win.lbl_queue = QLabel("0")
    win.lbl_stats_at = QLabel("\u0435\u0449\u0451 \u043d\u0435 \u043e\u0431\u043d\u043e\u0432\u043b\u044f\u043b\u043e\u0441\u044c")
    win.lbl_stats_note = QLabel("")
    for lbl in (
        win.lbl_active,
        win.lbl_total,
        win.lbl_inv,
        win.lbl_interviews,
        win.lbl_refusals,
        win.lbl_unread,
        win.lbl_views,
        win.lbl_shows,
        win.lbl_queue,
    ):
        lbl.setObjectName("statsValue")
    win.lbl_stats_at.setObjectName("mutedLabel")
    win.lbl_stats_note.setObjectName("mutedLabel")
    win.lbl_stats_note.setWordWrap(True)
    sf.addRow("\u041e\u0436\u0438\u0434\u0430\u043d\u0438\u0435:", win.lbl_active)
    sf.addRow("\u0412\u0441\u0435\u0433\u043e \u0432 \u043e\u0442\u043a\u043b\u0438\u043a\u0430\u0445:", win.lbl_total)
    sf.addRow("\u041f\u0440\u0438\u0433\u043b\u0430\u0448\u0435\u043d\u0438\u044f:", win.lbl_inv)
    sf.addRow("\u0421\u043e\u0431\u0435\u0441\u0435\u0434\u043e\u0432\u0430\u043d\u0438\u044f:", win.lbl_interviews)
    sf.addRow("\u041e\u0442\u043a\u0430\u0437\u044b:", win.lbl_refusals)
    sf.addRow("\u041d\u0435\u043f\u0440\u043e\u0447\u0438\u0442\u0430\u043d\u043d\u044b\u0435 \u0447\u0430\u0442\u044b:", win.lbl_unread)
    sf.addRow("\u041f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u044b:", win.lbl_views)
    sf.addRow("\u041f\u043e\u043a\u0430\u0437\u044b:", win.lbl_shows)
    sf.addRow("\u041d\u043e\u0432\u044b\u0435 \u0432 \u043e\u0447\u0435\u0440\u0435\u0434\u0438:", win.lbl_queue)
    sf.addRow("\u041e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u043e:", win.lbl_stats_at)
    sf.addRow("", win.lbl_stats_note)
    sl.addWidget(stats_box)

    guides = QHBoxLayout()
    win.btn_guide = ScaleButton("\u0413\u0430\u0439\u0434: \u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0430 HH", role="ghost")
    win.btn_guide.clicked.connect(lambda: win.show_text("\u0413\u0430\u0439\u0434: \u0441\u0442\u0430\u0442\u0438\u0441\u0442\u0438\u043a\u0430 HH", GUIDE_STATS))
    win.btn_guide_hk = ScaleButton("\u0413\u0430\u0439\u0434: \u0445\u043e\u0442\u043a\u0435\u0439", role="ghost")
    win.btn_guide_hk.clicked.connect(lambda: win.show_text("\u0413\u0430\u0439\u0434: \u0445\u043e\u0442\u043a\u0435\u0439", GUIDE_HOTKEY))
    guides.addWidget(win.btn_guide)
    guides.addWidget(win.btn_guide_hk)
    guides.addStretch(1)
    sl.addLayout(guides)
    sl.addStretch(1)
    page_s.setWidget(sw)
    win.pages.addWidget(page_s)

    # === PAGE 2: Settings ===
    page_set = QScrollArea()
    page_set.setWidgetResizable(True)
    page_set.setFrameShape(QScrollArea.NoFrame)
    setw = QWidget()
    setl = QVBoxLayout(setw)
    setl.setSpacing(14)

    hk_box = QGroupBox("\u0425\u043e\u0442\u043a\u0435\u0439")
    hk_l = QVBoxLayout(hk_box)
    win.lbl_hk_status = QLabel("")
    win.lbl_hk_status.setObjectName("mutedLabel")
    win.lbl_hk_status.setWordWrap(True)
    hk_l.addWidget(win.lbl_hk_status)
    hk_btns = QHBoxLayout()
    win.btn_set_hk = ScaleButton("\u041d\u0430\u0437\u043d\u0430\u0447\u0438\u0442\u044c", role="primary")
    win.btn_set_hk.clicked.connect(win.capture_hotkey)
    win.btn_test_hk = ScaleButton("\u041f\u0440\u043e\u0432\u0435\u0440\u0438\u0442\u044c")
    win.btn_test_hk.clicked.connect(win.test_hotkey)
    win.btn_reset_hk = ScaleButton("\u0421\u0431\u0440\u043e\u0441 Ctrl+Alt+Q", role="ghost")
    win.btn_reset_hk.clicked.connect(win.reset_hotkey)
    for b in (win.btn_set_hk, win.btn_test_hk, win.btn_reset_hk):
        hk_btns.addWidget(b)
    hk_l.addLayout(hk_btns)
    setl.addWidget(hk_box)

    opt = QGroupBox("\u041e\u043f\u0446\u0438\u0438")
    ol = QVBoxLayout(opt)
    win.chk_sound = QCheckBox("\u0417\u0432\u0443\u043a (\u00d73) \u043f\u0440\u0438 \u043d\u043e\u0432\u043e\u0439 \u0432\u0430\u043a\u0430\u043d\u0441\u0438\u0438")
    win.chk_sound.setChecked(bool(win.cfg.get("sound_enabled", True)))
    win.chk_sound.stateChanged.connect(win.save_opts)
    win.chk_dnd = QCheckBox("DND \u2014 \u0431\u0435\u0437 \u0437\u0432\u0443\u043a\u0430")
    win.chk_dnd.setChecked(bool(win.cfg.get("dnd", False)))
    win.chk_dnd.stateChanged.connect(win.save_opts)
    win.chk_min = QCheckBox("\u0421\u0432\u043e\u0440\u0430\u0447\u0438\u0432\u0430\u0442\u044c \u043f\u0440\u0435\u0434\u044b\u0434\u0443\u0449\u0435\u0435 \u043e\u043a\u043d\u043e \u043f\u043e \u0445\u043e\u0442\u043a\u0435\u044e")
    win.chk_min.setChecked(bool(win.cfg.get("minimize_previous", False)))
    win.chk_min.stateChanged.connect(win.save_opts)
    win.chk_autostart = QCheckBox("\u0412\u043a\u043b\u044e\u0447\u0430\u0442\u044c \u043f\u0440\u0438 \u0437\u0430\u043f\u0443\u0441\u043a\u0435 \u0441\u0438\u0441\u0442\u0435\u043c\u044b")
    win.chk_autostart.setChecked(
        bool(win.cfg.get("autostart_enabled", False)) or is_autostart_enabled()
    )
    win.chk_autostart.stateChanged.connect(win.on_autostart_changed)
    for chk in (win.chk_sound, win.chk_dnd, win.chk_min, win.chk_autostart):
        chk.setMinimumHeight(36)
        ol.addWidget(chk)
    setl.addWidget(opt)

    theme_box = QGroupBox("\u0422\u0435\u043c\u0430")
    tl = QHBoxLayout(theme_box)
    win.cmb_theme = QComboBox()
    for tid in THEME_IDS:
        win.cmb_theme.addItem(THEME_LABELS.get(tid, tid), tid)
    cur = str(win.cfg.get("ui_theme") or "04")
    idx = max(0, win.cmb_theme.findData(cur))
    win.cmb_theme.setCurrentIndex(idx)
    win.cmb_theme.currentIndexChanged.connect(win.on_theme_changed)
    tl.addWidget(win.cmb_theme)
    setl.addWidget(theme_box)

    log_title = QLabel("\u041b\u043e\u0433")
    log_title.setObjectName("sectionTitle")
    setl.addWidget(log_title)
    win.log_view = QTextEdit()
    win.log_view.setReadOnly(True)
    win.log_view.setMinimumHeight(220)
    setl.addWidget(win.log_view)
    setl.addStretch(1)
    page_set.setWidget(setw)
    win.pages.addWidget(page_set)

    # ----- Bottom metrics strip (ref 04) -----
    strip = QFrame()
    strip.setObjectName("statsStrip")
    sfh = QHBoxLayout(strip)
    sfh.setContentsMargins(10, 6, 10, 6)
    sfh.setSpacing(6)

    w_tot, win.lbl_strip_total = _metric("st_total.png", "Total")
    w_new, win.lbl_strip_new = _metric("st_new.png", "New")
    w_app, win.lbl_strip_applied = _metric("st_applied.png", "Applied")
    w_rep, win.lbl_strip_replies = _metric("st_replies.png", "Replies")
    w_int, win.lbl_strip_interviews = _metric("st_interview.png", "Interviews")
    w_off, win.lbl_strip_offers = _metric("st_offer.png", "Offers")
    for w in (w_tot, w_new, w_app, w_rep, w_int, w_off):
        sfh.addWidget(w)
    sfh.addStretch(1)
    win.lbl_strip_updated = QLabel("")
    win.lbl_strip_updated.setObjectName("mutedLabel")
    sfh.addWidget(win.lbl_strip_updated)
    outer.addWidget(strip)

    # F5 / F9 shortcuts
    from PySide6.QtGui import QKeySequence, QShortcut

    QShortcut(QKeySequence("F5"), win, activated=win.run_search)
    QShortcut(QKeySequence("F9"), win, activated=win.run_stats)
