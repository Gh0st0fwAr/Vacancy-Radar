# -*- coding: utf-8 -*-
"""Vue-stack scorer tests do not apply on python-only (profile keywords)."""
from __future__ import annotations

from radar.scorer import score_vacancy


def test_empty_profile_does_not_accept_unrelated_vue():
    sc, reasons, ok = score_vacancy(
        title="Fullstack Vue 3",
        snippet="Vue3 Nuxt TypeScript remote",
        salary_text="160000",
        schedule="remote",
        gate_threshold=80,
        profile={"must_have_keywords": ["Linux"], "search_keywords": ["Linux"]},
    )
    assert ok is False
    assert sc < 80


def test_profile_accepts_when_must_have_hits():
    sc, reasons, ok = score_vacancy(
        title="Linux L1 technical support",
        snippet="Linux support L1 Python remote",
        schedule="remote",
        salary_floor=60000,
        gate_threshold=80,
        profile={
            "must_have_keywords": ["Linux", "support"],
            "search_keywords": ["Linux", "L1", "Python"],
        },
    )
    assert ok is True
    assert sc >= 80
