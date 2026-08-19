# -*- coding: utf-8 -*-
"""Tests for profile_packs: save/load roundtrip with temp DATA."""
from __future__ import annotations

import json

import pytest

from radar.profile_packs import (
    _sanitize_name,
    export_pack_to_path,
    import_pack_from_path,
    list_packs,
    load_pack,
    save_pack,
)


@pytest.fixture
def packs_env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    uploads = data / "uploads"
    uploads.mkdir()
    packs = data / "profile_packs"

    monkeypatch.setattr("radar.config.DATA", data)
    monkeypatch.setattr("radar.config.CONFIG_PATH", data / "config.json")
    monkeypatch.setattr("radar.profile_packs.DATA", data)
    monkeypatch.setattr("radar.profile_packs.PACKS_DIR", packs)
    monkeypatch.setattr("radar.profile_packs.INDEX_PATH", packs / "index.json")

    monkeypatch.setattr("radar.user_profile.DATA", data)
    monkeypatch.setattr("radar.user_profile.PROFILE_PATH", data / "user_profile.json")
    monkeypatch.setattr("radar.user_profile.UPLOADS_DIR", uploads)
    monkeypatch.setattr("radar.user_profile.RESUME_TEXT_CACHE", uploads / "resume_text.txt")

    monkeypatch.setattr("radar.preferences.DATA", data)
    monkeypatch.setattr("radar.preferences.PREFERENCES_PATH", data / "preferences.json")
    monkeypatch.setattr("radar.preferences.UPLOAD_LOG_PATH", data / "upload_log.jsonl")

    monkeypatch.setattr("radar.references.DATA", data)
    monkeypatch.setattr("radar.references.REFERENCES_PATH", data / "references.json")

    monkeypatch.setattr("radar.scoring_state.DATA", data)
    monkeypatch.setattr("radar.scoring_state.STATE_PATH", data / "scoring_state.json")

    monkeypatch.setattr("radar.scoring_calibration.DATA", data)
    monkeypatch.setattr("radar.scoring_calibration.CALIBRATION_JSON", data / "scoring_calibration.json")
    monkeypatch.setattr("radar.scoring_calibration.CALIBRATION_MD", data / "scoring_calibration.md")

    return data


def test_sanitize_name():
    assert _sanitize_name("Hello World!") == "Hello_World"
    assert _sanitize_name("a" * 100) == "a" * 64
    assert _sanitize_name("") == "pack"
    assert _sanitize_name("  my-pack_01  ") == "my-pack_01"


def test_save_and_list(packs_env):
    from radar.preferences import save_preferences
    from radar.user_profile import save_profile

    save_profile({"resume_path": "", "portfolio_url": "https://example.com"})
    save_preferences({"desirable": ["Vue"], "neutral": [], "undesirable": [], "reject": []})

    result = save_pack("test_pack")
    assert result["ok"] is True
    assert result["name"] == "test_pack"
    assert "test_pack" in list_packs()


def test_save_load_roundtrip(packs_env):
    from radar.preferences import load_preferences, save_preferences
    from radar.user_profile import load_profile, save_profile

    resume = packs_env / "uploads" / "test_resume.txt"
    resume.write_text("I am a Vue developer with 6 years of experience.")

    save_profile({
        "resume_path": str(resume),
        "resume_filename": "test_resume.txt",
        "portfolio_url": "https://mysite.com",
        "github_url": "https://github.com/me",
    })
    save_preferences({
        "desirable": ["Vue", "Nuxt"],
        "neutral": ["Python"],
        "undesirable": [],
        "reject": ["Angular"],
    })

    save_pack("roundtrip")

    save_profile({"resume_path": "", "portfolio_url": ""})
    save_preferences({"desirable": [], "neutral": [], "undesirable": [], "reject": []})

    load_pack("roundtrip")

    profile = load_profile()
    assert profile["portfolio_url"] == "https://mysite.com"
    assert profile["resume_filename"] == "test_resume.txt"

    prefs = load_preferences()
    assert "Vue" in prefs["desirable"]
    assert "Angular" in prefs["reject"]


def test_import_pack(packs_env, tmp_path):
    pack_data = {
        "name": "imported",
        "user_profile": {"resume_path": "", "portfolio_url": "https://imp.com"},
        "preferences": {"desirable": ["React"], "neutral": [], "undesirable": [], "reject": []},
        "references": {"urls": [], "calibration": None},
        "scoring_state": {},
        "scoring_calibration": {},
        "resume_base64": "",
        "resume_filename": "",
    }
    src = tmp_path / "export" / "imported.json"
    src.parent.mkdir()
    src.write_text(json.dumps(pack_data), encoding="utf-8")

    result = import_pack_from_path(src)
    assert result["ok"] is True
    assert "imported" in list_packs()


def test_load_nonexistent_raises(packs_env):
    with pytest.raises(FileNotFoundError):
        load_pack("nonexistent_pack")
