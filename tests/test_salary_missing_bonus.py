# -*- coding: utf-8 -*-
from __future__ import annotations

from radar.scorer import score_vacancy


def test_missing_salary_bonus_when_reaches_70():
    sc, reasons, ok = score_vacancy(
        title="Linux L1 support remote",
        snippet="Linux support L1 Python remote Junior",
        salary_text="",
        schedule="remote",
        salary_floor=60000,
        gate_threshold=80,
        profile=PROFILE,
    )
    assert ok
    assert sc >= 70
    assert any("+20" in r and "70+" in r for r in reasons)


def test_missing_salary_no_bonus_if_still_below_70():
    sc, reasons, ok = score_vacancy(
        title="Remote PostgreSQL",
        snippet="PostgreSQL remote only",
        salary_text="",
        schedule="remote",
        salary_floor=60000,
        gate_threshold=80,
        profile=PROFILE,
    )
    assert ok
    assert sc < 70
    assert any("< 70" in r for r in reasons)


def test_salary_floor_bonus_17():
    sc, reasons, ok = score_vacancy(
        title="Vue 3 TypeScript developer remote",
        snippet="Vue3 TypeScript remote",
        salary_text="130000",
        schedule="remote",
    )
    assert ok
    assert any("+17 ЗП≥120000" in r for r in reasons)


def test_salary_good_bonus_20():
    sc, reasons, ok = score_vacancy(
        title="Vue 3 TypeScript developer remote",
        snippet="Vue3 TypeScript remote",
        salary_text="160000",
        schedule="remote",
    )
    assert ok
    assert any("+20 ЗП≥140000" in r for r in reasons)
