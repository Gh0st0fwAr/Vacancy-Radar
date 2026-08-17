# -*- coding: utf-8 -*-
"""Tests for Cursor / rules scoring dispatcher."""
from __future__ import annotations

import json
from unittest.mock import patch

from radar.cursor_score import score_for_search, scoring_mode


class TestScoringMode:
    def test_default_cursor(self):
        assert scoring_mode({"scoring_mode": "cursor"}) == "cursor"
        assert scoring_mode({"scoring_mode": "rules"}) == "rules"
        assert scoring_mode({"scoring_mode": "weird"}) == "cursor"

    def test_python_only_forces_rules(self):
        assert scoring_mode({"scoring_mode": "cursor", "python_only": True}) == "rules"


class TestScoreForSearchRules:
    def test_rules_mode_uses_local_scorer(self):
        cfg = {
            "scoring_mode": "rules",
            "score_threshold": 65,
            "salary_floor": 120000,
            "cursor_api_key": "",
        }
        sc, reasons, ok, meta = score_for_search(
            title="Vue 3 TypeScript remote Middle",
            snippet="Vue3 TypeScript remote Middle Pinia",
            salary_text="",
            schedule="remote",
            company="TestCo",
            cfg=cfg,
        )
        assert meta["source"] == "rules"
        assert ok is True
        assert sc >= 65
        assert any("Vue" in r or "remote" in r for r in reasons)


class TestScoreForSearchCursorNoRulesFallback:
    def test_cursor_mode_without_key_does_not_use_rules(self):
        cfg = {
            "scoring_mode": "cursor",
            "score_threshold": 65,
            "salary_floor": 120000,
            "cursor_api_key": "",
        }
        sc, reasons, ok, meta = score_for_search(
            title="Vue 3 TypeScript remote",
            snippet="Vue3 TypeScript remote",
            schedule="remote",
            cfg=cfg,
        )
        assert meta["source"] == "cursor_unavailable"
        assert ok is False
        assert sc == 0
        assert "cursor-unavailable" in reasons


class TestCursorBridgeParse:
    def test_extract_json_shape_documented(self):
        # Mirror bridge contract used by Node script
        sample = {"score": 78, "accept": True, "reasons": ["Vue 3", "remote"]}
        raw = json.dumps(sample)
        parsed = json.loads(raw)
        assert parsed["score"] == 78
        assert parsed["accept"] is True


class TestCursorViaMock:
    def test_cursor_path_when_bridge_returns_ok(self):
        cfg = {
            "scoring_mode": "cursor",
            "score_threshold": 65,
            "salary_floor": 120000,
            "cursor_api_key": "test-key",
            "cursor_model": "composer-2.5",
            "cursor_score_timeout_sec": 30,
        }
        fake = {
            "ok": True,
            "score": 82,
            "accept": True,
            "reasons": ["Vue 3 fit", "remote"],
            "source": "cursor",
            "elapsed_ms": 1234,
            "usage": {"inputTokens": 1000, "outputTokens": 80, "totalTokens": 1080},
        }
        with patch("radar.cursor_score._api_key", return_value="test-key"):
            with patch("radar.cursor_score.BRIDGE") as br:
                br.exists.return_value = True
                with patch("radar.cursor_score._via_cursor", return_value=fake):
                    sc, reasons, ok, meta = score_for_search(
                        title="Fullstack Vue",
                        snippet="Vue3 Node remote",
                        schedule="remote",
                        cfg=cfg,
                    )
        assert sc == 82
        assert ok is True
        assert meta["source"] == "cursor"
        assert meta["usage"]["totalTokens"] == 1080
        assert "Vue 3 fit" in reasons
