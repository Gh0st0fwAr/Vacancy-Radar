# -*- coding: utf-8 -*-
"""Tests for scoring_calibration: merge_preferences_from_suggestion union vs empty."""
from __future__ import annotations

import pytest

from radar.scoring_calibration import (
    load_calibration,
    merge_preferences_from_suggestion,
    save_calibration,
    write_calibration_md,
)


@pytest.fixture
def cal_env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setattr("radar.config.DATA", data)
    monkeypatch.setattr("radar.scoring_calibration.DATA", data)
    monkeypatch.setattr("radar.scoring_calibration.CALIBRATION_JSON", data / "scoring_calibration.json")
    monkeypatch.setattr("radar.scoring_calibration.CALIBRATION_MD", data / "scoring_calibration.md")
    return data


def test_merge_union_keeps_existing_and_adds_new():
    existing = {
        "desirable": ["Vue", "TypeScript", "Nuxt"],
        "neutral": ["Python"],
        "undesirable": ["Angular", "Java"],
        "reject": ["PHP"],
    }
    suggested = {
        "desirable": ["vue", "nuxt", "React", "AI"],
        "neutral": ["python", "Go"],
        "undesirable": ["angular"],
        "reject": ["php", "C++"],
    }
    result = merge_preferences_from_suggestion(existing, suggested)
    assert result["desirable"] == ["Vue", "TypeScript", "Nuxt", "React", "AI"]
    assert result["neutral"] == ["Python", "Go"]
    assert result["undesirable"] == ["Angular", "Java"]
    assert result["reject"] == ["PHP", "C++"]


def test_merge_empty_existing_uses_suggested():
    existing = {
        "desirable": [],
        "neutral": [],
        "undesirable": [],
        "reject": [],
    }
    suggested = {
        "desirable": ["Vue", "Nuxt"],
        "neutral": ["Python"],
        "undesirable": ["Angular"],
        "reject": ["PHP"],
    }
    result = merge_preferences_from_suggestion(existing, suggested)
    assert result["desirable"] == ["Vue", "Nuxt"]
    assert result["neutral"] == ["Python"]
    assert result["undesirable"] == ["Angular"]
    assert result["reject"] == ["PHP"]


def test_merge_empty_suggested_keeps_existing():
    existing = {
        "desirable": ["Vue", "TypeScript"],
        "neutral": [],
        "undesirable": [],
        "reject": [],
    }
    suggested = {
        "desirable": [],
        "neutral": [],
        "undesirable": [],
        "reject": [],
    }
    result = merge_preferences_from_suggestion(existing, suggested)
    assert result["desirable"] == ["Vue", "TypeScript"]


def test_merge_case_insensitive_dedupe():
    existing = {"desirable": ["VUE"], "neutral": [], "undesirable": [], "reject": []}
    suggested = {"desirable": ["vue", "AI"], "neutral": [], "undesirable": [], "reject": []}
    result = merge_preferences_from_suggestion(existing, suggested)
    assert result["desirable"] == ["VUE", "AI"]


def test_merge_partial_buckets():
    existing = {
        "desirable": ["Vue"],
        "neutral": [],
        "undesirable": ["Java"],
        "reject": [],
    }
    suggested = {
        "desirable": ["Vue", "React"],
        "neutral": ["Go"],
        "undesirable": [],
        "reject": ["PHP"],
    }
    result = merge_preferences_from_suggestion(existing, suggested)
    assert result["desirable"] == ["Vue", "React"]
    assert result["neutral"] == ["Go"]
    assert result["undesirable"] == ["Java"]
    assert result["reject"] == ["PHP"]


def test_save_load_calibration(cal_env):
    data = {
        "updated_at": "2026-01-01T00:00:00+00:00",
        "source": "profile_upload",
        "profile": {
            "skills": ["Vue", "TS"],
            "stack": ["Vue 3"],
            "level": "middle",
            "notes": "Good profile",
            "suggested_preferences": {"desirable": ["Vue"], "neutral": [], "undesirable": [], "reject": []},
        },
        "preferences_analysis": {"notes": "", "buckets_echo": {}},
        "references_analysis": {},
        "raw_cursor": "test raw",
    }
    save_calibration(data)
    loaded = load_calibration()
    assert loaded["source"] == "profile_upload"
    assert loaded["profile"]["skills"] == ["Vue", "TS"]


def test_write_calibration_md(cal_env):
    data = {
        "updated_at": "2026-08-01",
        "source": "profile_upload",
        "profile": {
            "skills": ["Vue"],
            "stack": ["Vue 3"],
            "level": "middle",
            "notes": "Good",
            "suggested_preferences": {"desirable": ["Vue"], "neutral": [], "undesirable": [], "reject": []},
        },
        "preferences_analysis": {},
        "references_analysis": {},
        "raw_cursor": "",
    }
    write_calibration_md(data)
    md_path = cal_env / "scoring_calibration.md"
    assert md_path.is_file()
    content = md_path.read_text(encoding="utf-8")
    assert "Scoring Calibration" in content
    assert "middle" in content
