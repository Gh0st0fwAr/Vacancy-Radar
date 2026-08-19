# -*- coding: utf-8 -*-
"""Tests for scoring_state: fingerprint + dirty/sync logic."""
from __future__ import annotations

import json

import pytest


@pytest.fixture
def state_env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    uploads = data / "uploads"
    uploads.mkdir()

    monkeypatch.setattr("radar.config.DATA", data)
    monkeypatch.setattr("radar.scoring_state.DATA", data)
    monkeypatch.setattr("radar.scoring_state.STATE_PATH", data / "scoring_state.json")

    monkeypatch.setattr("radar.user_profile.DATA", data)
    monkeypatch.setattr("radar.user_profile.PROFILE_PATH", data / "user_profile.json")
    monkeypatch.setattr("radar.user_profile.UPLOADS_DIR", uploads)
    monkeypatch.setattr("radar.user_profile.RESUME_TEXT_CACHE", uploads / "resume_text.txt")

    monkeypatch.setattr("radar.preferences.DATA", data)
    monkeypatch.setattr("radar.preferences.PREFERENCES_PATH", data / "preferences.json")

    monkeypatch.setattr("radar.references.DATA", data)
    monkeypatch.setattr("radar.references.REFERENCES_PATH", data / "references.json")

    return data


def test_load_state_default(state_env):
    from radar.scoring_state import load_state

    st = load_state()
    assert st["profile_synced"] is False
    assert st["preferences_synced"] is False
    assert st["references_synced"] is False
    assert st["profile_fingerprint"] == ""


def test_fingerprint_profile_changes_with_file(state_env, tmp_path):
    from radar.scoring_state import fingerprint_profile
    from radar.user_profile import save_profile

    save_profile({"resume_path": "", "portfolio_url": "", "github_url": ""})
    fp1 = fingerprint_profile()

    resume = state_env / "uploads" / "test.txt"
    resume.write_text("My resume content")
    save_profile({
        "resume_path": str(resume),
        "portfolio_url": "https://example.com",
        "github_url": "https://github.com/test",
    })
    fp2 = fingerprint_profile()

    assert fp1 != fp2
    assert len(fp2) == 24


def test_fingerprint_preferences_deterministic(state_env):
    from radar.preferences import save_preferences
    from radar.scoring_state import fingerprint_preferences

    save_preferences({
        "desirable": ["Vue", "TypeScript"],
        "neutral": [],
        "undesirable": ["Angular"],
        "reject": [],
    })
    fp1 = fingerprint_preferences()
    fp2 = fingerprint_preferences()
    assert fp1 == fp2
    assert len(fp1) == 24


def test_fingerprint_preferences_changes(state_env):
    from radar.preferences import save_preferences
    from radar.scoring_state import fingerprint_preferences

    save_preferences({
        "desirable": ["Vue"],
        "neutral": [],
        "undesirable": [],
        "reject": [],
    })
    fp1 = fingerprint_preferences()

    save_preferences({
        "desirable": ["Vue", "Nuxt"],
        "neutral": [],
        "undesirable": [],
        "reject": [],
    })
    fp2 = fingerprint_preferences()
    assert fp1 != fp2


def test_mark_synced_and_dirty(state_env):
    from radar.preferences import save_preferences
    from radar.scoring_state import (
        load_state,
        mark_preferences_dirty,
        mark_preferences_synced,
    )

    save_preferences({
        "desirable": ["Vue"],
        "neutral": [],
        "undesirable": [],
        "reject": [],
    })

    mark_preferences_synced()
    st = load_state()
    assert st["preferences_synced"] is True
    assert st["preferences_fingerprint"] != ""
    assert st["preferences_analyzed_at"] != ""

    mark_preferences_dirty()
    st = load_state()
    assert st["preferences_synced"] is False


def test_recompute_detects_mismatch(state_env):
    from radar.preferences import save_preferences
    from radar.scoring_state import load_state, mark_preferences_synced, recompute_sync_flags

    save_preferences({
        "desirable": ["Vue"],
        "neutral": [],
        "undesirable": [],
        "reject": [],
    })
    mark_preferences_synced()

    save_preferences({
        "desirable": ["Vue", "React"],
        "neutral": [],
        "undesirable": [],
        "reject": [],
    })

    st = recompute_sync_flags()
    assert st["preferences_synced"] is False


def test_recompute_keeps_synced_when_matching(state_env):
    from radar.preferences import save_preferences
    from radar.scoring_state import mark_preferences_synced, recompute_sync_flags

    save_preferences({
        "desirable": ["Vue"],
        "neutral": [],
        "undesirable": [],
        "reject": [],
    })
    mark_preferences_synced()

    st = recompute_sync_flags()
    assert st["preferences_synced"] is True
