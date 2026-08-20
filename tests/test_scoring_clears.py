# -*- coding: utf-8 -*-
"""Tests for scoring_actions clear/upload edge cases."""
from __future__ import annotations

import json

import pytest

from radar.config import save_json
from radar.hh_search_url import NEUTRAL_HH_SEARCH_URL
from radar.preferences import DEFAULT_PREFERENCES, load_preferences, save_preferences
from radar.references import DEFAULT_REFERENCES, load_references, save_references
from radar.scoring_calibration import (
    DEFAULT_CALIBRATION,
    load_calibration,
    save_calibration,
)
from radar.scoring_state import (
    load_state,
    mark_preferences_dirty,
    mark_preferences_synced,
    mark_profile_dirty,
    mark_profile_synced,
    mark_references_dirty,
    mark_references_synced,
)
from radar.user_profile import load_profile, save_profile


@pytest.fixture
def clears_env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    uploads = data / "uploads"
    uploads.mkdir()
    config_path = data / "config.json"
    profile_path = data / "user_profile.json"
    prefs_path = data / "preferences.json"
    refs_path = data / "references.json"
    cal_json = data / "scoring_calibration.json"
    cal_md = data / "scoring_calibration.md"
    state_path = data / "scoring_state.json"

    monkeypatch.setattr("radar.config.DATA", data)
    monkeypatch.setattr("radar.config.CONFIG_PATH", config_path)
    monkeypatch.setattr("radar.user_profile.DATA", data)
    monkeypatch.setattr("radar.user_profile.PROFILE_PATH", profile_path)
    monkeypatch.setattr("radar.user_profile.UPLOADS_DIR", uploads)
    monkeypatch.setattr("radar.user_profile.RESUME_TEXT_CACHE", uploads / "resume_text.txt")
    monkeypatch.setattr("radar.preferences.DATA", data)
    monkeypatch.setattr("radar.preferences.PREFERENCES_PATH", prefs_path)
    monkeypatch.setattr("radar.preferences.UPLOAD_LOG_PATH", data / "upload_log.jsonl")
    monkeypatch.setattr("radar.references.DATA", data)
    monkeypatch.setattr("radar.references.REFERENCES_PATH", refs_path)
    monkeypatch.setattr("radar.scoring_calibration.DATA", data)
    monkeypatch.setattr("radar.scoring_calibration.CALIBRATION_JSON", cal_json)
    monkeypatch.setattr("radar.scoring_calibration.CALIBRATION_MD", cal_md)
    monkeypatch.setattr("radar.scoring_state.DATA", data)
    monkeypatch.setattr("radar.scoring_state.STATE_PATH", state_path)

    return {
        "data": data,
        "config_path": config_path,
        "profile_path": profile_path,
        "prefs_path": prefs_path,
        "refs_path": refs_path,
        "cal_json": cal_json,
        "cal_md": cal_md,
        "state_path": state_path,
    }


def _seed_populated(clears_env):
    """Profile, prefs, refs, calibration, config — all non-empty."""
    save_json(
        clears_env["config_path"],
        {
            "cursor_api_key": "secret-key-123",
            "score_threshold": 77,
            "hh_search_url": "https://hh.ru/search/vacancy?text=Vue",
        },
    )
    resume = clears_env["data"] / "uploads" / "cv.txt"
    resume.write_text("Vue developer resume", encoding="utf-8")
    save_profile(
        {
            "resume_path": str(resume),
            "resume_filename": "cv.txt",
            "portfolio_url": "https://example.com/portfolio",
            "github_url": "https://github.com/test",
            "activity_sphere": "Разработчик",
        }
    )
    save_preferences(
        {
            "desirable": ["Vue", "TypeScript"],
            "neutral": ["Python"],
            "undesirable": ["Angular"],
            "reject": ["PHP"],
        }
    )
    save_references(
        {
            "urls": ["https://hh.ru/vacancy/111", "https://hh.ru/vacancy/222"],
            "calibration": {"summary": "good fits"},
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
    )
    save_calibration(
        {
            "updated_at": "2026-01-01T00:00:00+00:00",
            "source": "references_upload",
            "profile": {
                "skills": ["Vue"],
                "stack": ["Vue 3"],
                "level": "middle",
                "notes": "Strong frontend",
                "suggested_preferences": {
                    "desirable": ["Vue"],
                    "neutral": [],
                    "undesirable": [],
                    "reject": [],
                },
            },
            "preferences_analysis": {"notes": "prefs notes", "buckets_echo": {"desirable": ["Vue"]}},
            "references_analysis": {"summary": "ref summary"},
            "raw_cursor": "raw output",
        }
    )
    mark_profile_synced()
    mark_preferences_synced()
    mark_references_synced()


def test_clear_profile_action(clears_env):
    from radar.scoring_actions import clear_profile_action

    _seed_populated(clears_env)

    result = clear_profile_action()

    assert result["ok"] is True
    assert "snapshot" in result

    prefs = load_preferences()
    assert prefs == dict(DEFAULT_PREFERENCES)

    refs = load_references()
    assert refs.get("urls") == []
    assert refs.get("calibration") is None

    cal = load_calibration()
    assert cal.get("source") == ""
    assert cal.get("profile", {}).get("skills") == []
    assert cal.get("preferences_analysis") == {"notes": "", "buckets_echo": {}}
    assert cal.get("references_analysis") == {}

    profile = load_profile()
    assert profile.get("resume_path") == ""
    assert profile.get("portfolio_url") == ""
    assert profile.get("activity_sphere") == ""

    saved_cfg = json.loads(clears_env["config_path"].read_text(encoding="utf-8"))
    assert saved_cfg["cursor_api_key"] == "secret-key-123"
    assert saved_cfg["score_threshold"] == 77
    assert saved_cfg["hh_search_url"] == NEUTRAL_HH_SEARCH_URL

    st = load_state()
    assert st["profile_synced"] is False
    assert st["preferences_synced"] is False
    assert st["references_synced"] is False


def test_clear_preferences_action(clears_env):
    from radar.scoring_actions import clear_preferences_action

    _seed_populated(clears_env)

    result = clear_preferences_action()

    assert result["ok"] is True

    prefs = load_preferences()
    assert prefs == dict(DEFAULT_PREFERENCES)

    refs = load_references()
    assert refs.get("urls") == [
        "https://hh.ru/vacancy/111",
        "https://hh.ru/vacancy/222",
    ]

    cal = load_calibration()
    assert cal.get("preferences_analysis") == {"notes": "", "buckets_echo": {}}
    assert cal.get("profile", {}).get("suggested_preferences") == dict(DEFAULT_PREFERENCES)
    assert cal.get("references_analysis") == {"summary": "ref summary"}

    saved_cfg = json.loads(clears_env["config_path"].read_text(encoding="utf-8"))
    assert saved_cfg["cursor_api_key"] == "secret-key-123"


def test_clear_references_action(clears_env):
    from radar.scoring_actions import clear_references_action

    _seed_populated(clears_env)

    result = clear_references_action()

    assert result["ok"] is True

    refs = load_references()
    assert refs.get("urls") == []

    prefs = load_preferences()
    assert prefs["desirable"] == ["Vue", "TypeScript"]
    assert prefs["neutral"] == ["Python"]

    cal = load_calibration()
    assert cal.get("references_analysis") == {}
    assert cal.get("source") == ""
    assert cal.get("preferences_analysis", {}).get("notes") == "prefs notes"


def test_upload_references_action_empty_list(clears_env):
    from radar.scoring_actions import upload_references_action

    _seed_populated(clears_env)

    result = upload_references_action([])

    assert result["ok"] is True
    assert result.get("cleared") is True
    assert result.get("noop") is False

    refs = load_references()
    assert refs.get("urls") == []

    prefs = load_preferences()
    assert prefs["desirable"] == ["Vue", "TypeScript"]

    st = load_state()
    assert st["references_synced"] is True


def test_mark_dirty_synced_no_crash(clears_env):
    _seed_populated(clears_env)

    mark_profile_synced()
    mark_preferences_synced()
    mark_references_synced()
    st = load_state()
    assert st["profile_synced"] is True
    assert st["preferences_synced"] is True
    assert st["references_synced"] is True

    mark_profile_dirty()
    mark_preferences_dirty()
    mark_references_dirty()
    st = load_state()
    assert st["profile_synced"] is False
    assert st["preferences_synced"] is False
    assert st["references_synced"] is False
