# -*- coding: utf-8 -*-
"""Tests for gold-reference URLs and calibration prompt block."""
from __future__ import annotations

import pytest

from radar.references import (
    build_references_prompt_block,
    clear_calibration,
    load_references,
    save_references,
    set_calibration,
    set_urls,
)


@pytest.fixture
def refs_env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    path = data / "references.json"
    log_path = data / "upload_log.jsonl"
    monkeypatch.setattr("radar.config.DATA", data)
    monkeypatch.setattr("radar.references.DATA", data)
    monkeypatch.setattr("radar.references.REFERENCES_PATH", path)
    monkeypatch.setattr("radar.preferences.UPLOAD_LOG_PATH", log_path)
    return path


def test_set_urls_normalizes_and_dedupes(refs_env):
    saved = set_urls(["https://a.com", "https://A.com", "  ", "https://b.com"])
    assert saved["urls"] == ["https://a.com", "https://b.com"]
    assert load_references()["urls"] == saved["urls"]


def test_clear_calibration(refs_env):
    set_calibration(
        {
            "summary": "Strong Vue examples",
            "items": [{"url": "https://hh.ru/v/1", "score": 90}],
        }
    )
    cleared = clear_calibration()
    assert cleared["calibration"] is None
    assert load_references()["calibration"] is None


def test_build_references_prompt_block_empty(refs_env):
    save_references({"urls": [], "calibration": None})
    assert build_references_prompt_block() == ""


def test_build_references_prompt_block_with_calibration(refs_env):
    cal = {
        "summary": "Strong Vue fits",
        "analyzed_at": "2026-01-01T00:00:00+00:00",
        "items": [
            {
                "url": "https://hh.ru/vacancy/123",
                "score": 90,
                "reasons": ["Vue 3", "remote"],
                "excerpt": "Vue 3 TypeScript remote team",
            }
        ],
    }
    block = build_references_prompt_block({"urls": [], "calibration": cal})
    assert "reference calibration" in block.lower()
    assert "Strong Vue fits" in block
    assert "https://hh.ru/vacancy/123" in block
    assert "Vue 3 TypeScript remote team" in block
