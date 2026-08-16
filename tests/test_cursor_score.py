# -*- coding: utf-8 -*-
"""Tests for Cursor / rules scoring dispatcher."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from radar.cursor_score import score_for_search, scoring_mode


def _support_cfg(**extra):
    cfg = json.loads(
        (Path(__file__).resolve().parents[1] / "data" / "config.json").read_text(
            encoding="utf-8"
        )
    )
    cfg["cursor_api_key"] = ""
    cfg["scoring_mode"] = "rules"
    cfg.update(extra)
    return cfg


class TestScoringMode:
    def test_default_cursor(self):
        assert scoring_mode({"scoring_mode": "cursor"}) == "cursor"
        assert scoring_mode({"scoring_mode": "rules"}) == "rules"
        assert scoring_mode({"scoring_mode": "weird"}) == "cursor"

    def test_python_only_forces_rules(self):
        assert scoring_mode({"scoring_mode": "cursor", "python_only": True}) == "rules"


class TestScoreForSearchRules:
    def test_rules_mode_uses_local_scorer(self):
        cfg = _support_cfg()
        sc, reasons, ok, meta = score_for_search(
            title="Linux L1 support remote",
            snippet="Linux support L1 Python PostgreSQL remote Junior",
            salary_text="",
            schedule="remote",
            company="TestCo",
            cfg=cfg,
        )
        assert meta["source"] == "rules"
        assert ok is True
        assert sc >= 80
        assert any("remote" in r or "must:" in r for r in reasons)


class TestScoreForSearchCursorFallback:
    def test_cursor_falls_back_without_key(self):
        cfg = _support_cfg(scoring_mode="cursor", python_only=False)
        sc, reasons, ok, meta = score_for_search(
            title="Linux support remote",
            snippet="Linux support L1 remote",
            schedule="remote",
            cfg=cfg,
        )
        assert meta["source"] == "rules_fallback"
        assert "fallback:rules" in reasons
        assert isinstance(sc, int)


class TestCursorBridgeParse:
    def test_extract_json_shape_documented(self):
        sample = {"score": 78, "accept": True, "reasons": ["Linux", "remote"]}
        raw = json.dumps(sample)
        parsed = json.loads(raw)
        assert parsed["score"] == 78
        assert parsed["accept"] is True


class TestCursorViaMock:
    def test_cursor_path_when_bridge_returns_ok(self):
        cfg = _support_cfg(
            scoring_mode="cursor",
            python_only=False,
            cursor_api_key="test-key",
            cursor_model="composer-2.5",
            cursor_score_timeout_sec=30,
        )
        fake = {
            "ok": True,
            "score": 82,
            "accept": True,
            "reasons": ["Linux fit", "remote"],
            "source": "cursor",
            "elapsed_ms": 1234,
            "usage": {"inputTokens": 1000, "outputTokens": 80, "totalTokens": 1080},
        }
        with patch("radar.cursor_score._api_key", return_value="test-key"):
            with patch("radar.cursor_score.BRIDGE") as br:
                br.exists.return_value = True
                with patch("radar.cursor_score._via_cursor", return_value=fake):
                    sc, reasons, ok, meta = score_for_search(
                        title="Linux support",
                        snippet="Linux L1 remote",
                        schedule="remote",
                        cfg=cfg,
                    )
        assert sc == 82
        assert ok is True
        assert meta["source"] == "cursor"
        assert meta["usage"]["totalTokens"] == 1080
