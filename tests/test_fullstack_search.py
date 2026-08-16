# -*- coding: utf-8 -*-
from __future__ import annotations

from radar.scorer import score_vacancy


def test_fullstack_node_not_rejected():
    sc, reasons, ok = score_vacancy(
        title="Fullstack developer",
        snippet="Node.js TypeScript remote Middle",
        salary_text="",
        schedule="remote",
    )
    assert ok is True
    assert sc >= 65
    assert any("Fullstack" in r for r in reasons)


def test_fullstack_vue_gets_bonus():
    sc, reasons, ok = score_vacancy(
        title="Fullstack Vue 3",
        snippet="Vue3 Nuxt TypeScript remote",
        salary_text="160000",
        schedule="remote",
    )
    assert ok is True
    assert any("Fullstack" in r for r in reasons)
    assert sc >= 65


def test_vue2_scores():
    sc, reasons, ok = score_vacancy(
        title="Vue2 developer",
        snippet="Vue 2 TypeScript remote Middle",
        salary_text="",
        schedule="remote",
    )
    assert ok is True
    assert any("Vue 2" in r for r in reasons)
