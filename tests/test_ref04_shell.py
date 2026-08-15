# -*- coding: utf-8 -*-
from radar.queue_style import pill_label, status_kind
from radar.queue_store import Vacancy
from radar.themes import THEME_IDS, build_qss, get_palette
from radar.vacancy_delegate import VacancyCardDelegate


def test_ref04_qss_has_shell_selectors():
    qss = build_qss(get_palette("04"))
    for needle in ("navBtn", "detailTitle", "panelCard", "statsStrip", "vacancyList"):
        assert needle in qss


def test_pill_labels():
    v = Vacancy(id="1", title="T", company="C", url="u", score=80, status="new")
    assert pill_label("new", v) == "NEW"
    assert pill_label("apply", v) == "APPLIED"
    assert pill_label("invite", v) == "INVITE"
    v.hh_status = "interview"
    assert pill_label("invite", v) == "INTERVIEW"
    assert pill_label("pointer", v) == "NOW"


def test_status_kind_pointer_wins():
    v = Vacancy(
        id="1",
        title="T",
        company="C",
        url="u",
        score=80,
        status="applied",
        hh_status="invitation",
    )
    assert status_kind(v) == "invite"
    assert status_kind(v, is_active=True) == "pointer"


def test_vacancy_card_delegate_exists():
    assert VacancyCardDelegate is not None


def test_all_theme_ids_still_build():
    for tid in THEME_IDS:
        assert "QPushButton" in build_qss(get_palette(tid))
