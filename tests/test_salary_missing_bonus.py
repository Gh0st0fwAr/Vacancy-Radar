# -*- coding: utf-8 -*-
from __future__ import annotations

from radar.scorer import score_vacancy


PROFILE = {
    "must_have_keywords": ["Linux", "support", "техническая поддержка"],
    "search_keywords": ["Linux", "Python", "PostgreSQL", "L1", "L2"],
    "nice_to_have_keywords": ["знание английского", "advanced"],
    "hard_reject_keywords": ["1С"],
    "exclude_keywords": ["1С", "PHP", "казино", "крипто"],
}


def test_missing_salary_bonus_when_reaches_gate():
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
    assert sc >= 80
    assert any("+20" in r and "80+" in r for r in reasons)


def test_missing_salary_no_bonus_if_still_below_gate():
    # Only remote + one weak search hit -> below 80 even with +20
    sc, reasons, ok = score_vacancy(
        title="Remote PostgreSQL",
        snippet="PostgreSQL remote only",
        salary_text="",
        schedule="remote",
        salary_floor=60000,
        gate_threshold=80,
        profile=PROFILE,
    )
    # no must_have -> early low score
    assert sc < 80
    assert any("must_have" in r for r in reasons)
