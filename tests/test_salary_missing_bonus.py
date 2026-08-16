# -*- coding: utf-8 -*-
from __future__ import annotations

from radar.scorer import score_vacancy


def test_missing_salary_bonus_when_reaches_gate():
    sc, reasons, ok = score_vacancy(
        title="Vue 3 TypeScript developer remote",
        snippet="Vue3 TypeScript remote Middle",
        salary_text="",
        schedule="remote",
        gate_threshold=65,
    )
    assert ok
    assert sc >= 65
    assert any("+20" in r and "65+" in r for r in reasons)


def test_missing_salary_no_bonus_if_still_below_gate():
    sc, reasons, ok = score_vacancy(
        title="Fullstack developer remote",
        snippet="fullstack remote",
        salary_text="",
        schedule="remote",
        gate_threshold=65,
    )
    assert ok
    assert sc < 65
    assert any("< 65" in r for r in reasons)
