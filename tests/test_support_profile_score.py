# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

from radar.scorer import score_vacancy


def _cfg():
    return json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "config.example.json").read_text(
            encoding="utf-8"
        )
    )


def test_support_profile_accepts_linux_l1():
    cfg = _cfg()
    sc, reasons, ok = score_vacancy(
        title="Linux L1 technical support",
        snippet="Linux support L1 Python PostgreSQL English junior remote",
        salary_text="",
        schedule="remote",
        salary_floor=int(cfg["salary_floor"]),
        gate_threshold=int(cfg["score_threshold"]),
        profile=cfg,
    )
    assert ok
    assert sc >= 80
    assert any("must:Linux" in r for r in reasons)


def test_support_profile_rejects_1c():
    cfg = _cfg()
    sc, reasons, ok = score_vacancy(
        title="1C Linux support remote",
        snippet="1C Linux support remote",
        schedule="remote",
        salary_floor=60000,
        gate_threshold=80,
        profile=cfg,
    )
    assert sc == 0
    assert ok is False
    assert any("reject" in r.lower() for r in reasons)


def test_support_profile_rejects_without_must():
    cfg = _cfg()
    sc, reasons, ok = score_vacancy(
        title="Remote Python developer",
        snippet="Python PostgreSQL remote office barista coffee",
        schedule="remote",
        salary_floor=60000,
        gate_threshold=80,
        profile=cfg,
    )
    assert sc < 80
    assert any("must_have" in r for r in reasons)
