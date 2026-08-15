# -*- coding: utf-8 -*-
from __future__ import annotations

from radar.autostart import is_autostart_enabled, set_autostart
from radar.queue_style import colors_for_kind, is_blue, is_gray_apply, is_white, status_kind
from radar.queue_store import Vacancy
from radar.theme import apply_theme, current_theme_id
from radar.themes import THEME_IDS, THEME_LABELS, build_qss, get_palette


def test_all_themes_build_qss():
    for tid in THEME_IDS:
        p = get_palette(tid)
        qss = build_qss(p)
        assert p["ACCENT"] in qss
        assert "QListWidget" in qss
        assert tid in THEME_LABELS


def test_apply_theme_switches_tokens():
    apply_theme(None, "02")
    assert current_theme_id() == "02"
    from radar import theme as t

    assert t.ACCENT == get_palette("02")["ACCENT"]
    apply_theme(None, "04")
    assert current_theme_id() == "04"


def test_status_kind_and_colors():
    new_v = Vacancy(
        id="1",
        url="https://hh.ru/vacancy/1",
        title="Vue",
        company="A",
        status="new",
        score=80,
    )
    assert is_white(new_v)
    assert status_kind(new_v) == "new"
    fg, bg, stripe = colors_for_kind("new")
    assert fg.isValid() and stripe.isValid()

    applied = Vacancy(
        id="2",
        url="https://hh.ru/vacancy/2",
        title="Nuxt",
        company="B",
        status="applied",
        score=80,
        hh_status="awaiting",
    )
    assert is_gray_apply(applied)
    assert status_kind(applied) == "apply"

    invite = Vacancy(
        id="3",
        url="https://hh.ru/vacancy/3",
        title="Vue",
        company="C",
        status="applied",
        score=90,
        hh_status="invitation",
    )
    assert is_blue(invite)
    assert status_kind(invite) == "invite"
    assert status_kind(invite, is_active=True) == "pointer"
    pfg, pbg, pst = colors_for_kind("pointer")
    assert pbg.alpha() > 0
    assert pst.isValid()


def test_autostart_toggle_roundtrip(tmp_path, monkeypatch):
    fake = tmp_path / "VacancyRadar.lnk"
    monkeypatch.setattr("radar.autostart.startup_shortcut_path", lambda: fake)
    monkeypatch.setattr("radar.autostart._startup_dir", lambda: tmp_path)
    assert set_autostart(False)
    assert not is_autostart_enabled()

    def fake_run(*args, **kwargs):
        fake.write_text("lnk", encoding="utf-8")

        class R:
            returncode = 0

        return R()

    monkeypatch.setattr("subprocess.run", fake_run)
    msg = set_autostart(True)
    assert fake.exists()
    assert msg
    msg2 = set_autostart(False)
    assert not fake.exists()
    assert msg2
