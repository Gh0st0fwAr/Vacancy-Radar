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


def test_support_profile_accepts_linux_l1():
    sc, reasons, ok = score_vacancy(
        title="Linux L1 technical support",
        snippet="Linux support L1 Python PostgreSQL English junior remote",
        salary_text="",
        schedule="remote",
        salary_floor=60000,
        gate_threshold=80,
        profile=PROFILE,
    )
    assert ok
    assert sc >= 80
    assert any("must:Linux" in r for r in reasons)


def test_support_profile_rejects_1c():
    sc, reasons, ok = score_vacancy(
        title="1C Linux support remote",
        snippet="1C Linux support remote",
        schedule="remote",
        salary_floor=60000,
        gate_threshold=80,
        profile=PROFILE,
    )
    assert sc == 0
    assert ok is False
    assert any("reject" in r.lower() for r in reasons)


def test_support_profile_rejects_without_must():
    sc, reasons, ok = score_vacancy(
        title="Remote Python developer",
        snippet="Python PostgreSQL remote office barista coffee",
        schedule="remote",
        salary_floor=60000,
        gate_threshold=80,
        profile=PROFILE,
    )
    assert sc < 80
    assert any("must_have" in r for r in reasons)
