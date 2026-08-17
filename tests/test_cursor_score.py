# -*- coding: utf-8 -*-
"""Tests for Cursor SDK scoring (cursor-only, no hybrid/rules paths)."""
from __future__ import annotations

import json
from unittest.mock import patch

from radar.cursor_score import score_for_search


class TestCursorUnavailable:
    def test_no_key_returns_unavailable(self):
        cfg = {
            "score_threshold": 70,
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
        sample = {"score": 78, "accept": True, "reasons": ["Vue 3", "remote"]}
        raw = json.dumps(sample)
        parsed = json.loads(raw)
        assert parsed["score"] == 78
        assert parsed["accept"] is True


class TestCursorViaMock:
    def test_cursor_path_when_bridge_returns_ok(self):
        cfg = {
            "score_threshold": 65,
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

    def test_cursor_below_threshold_not_accepted(self):
        cfg = {
            "score_threshold": 70,
            "cursor_api_key": "test-key",
            "cursor_model": "composer-2.5",
            "cursor_score_timeout_sec": 30,
        }
        fake = {
            "ok": True,
            "score": 45,
            "accept": False,
            "reasons": ["some match"],
            "elapsed_ms": 500,
        }
        with patch("radar.cursor_score._api_key", return_value="test-key"):
            with patch("radar.cursor_score.BRIDGE") as br:
                br.exists.return_value = True
                with patch("radar.cursor_score._via_cursor", return_value=fake):
                    sc, reasons, ok, meta = score_for_search(
                        title="Java backend",
                        snippet="Java Spring",
                        cfg=cfg,
                    )
        assert sc == 45
        assert ok is False
        assert meta["source"] == "cursor"

    def test_cursor_bridge_failure_returns_zero(self):
        cfg = {
            "score_threshold": 70,
            "cursor_api_key": "test-key",
            "cursor_score_timeout_sec": 30,
        }
        with patch("radar.cursor_score._api_key", return_value="test-key"):
            with patch("radar.cursor_score.BRIDGE") as br:
                br.exists.return_value = True
                with patch("radar.cursor_score._via_cursor", return_value=None):
                    sc, reasons, ok, meta = score_for_search(
                        title="Vue 3",
                        snippet="Vue3 TS",
                        cfg=cfg,
                    )
        assert sc == 0
        assert ok is False
        assert meta["source"] == "cursor_failed"
