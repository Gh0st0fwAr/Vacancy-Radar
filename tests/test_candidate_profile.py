# -*- coding: utf-8 -*-
"""Tests for user-profile-based candidate scoring context."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from radar import cursor_score as cs
from radar import user_profile as up
from radar.candidate_profile import (
    build_candidate_block,
    is_profile_ready,
    links_dict,
    load_scoring_context,
    save_profile,
    set_links,
    upload_resume,
)


@pytest.fixture
def profile_env(tmp_path, monkeypatch):
    """Isolate profile storage to a temp VacancyRadar root."""
    data = tmp_path / "data"
    uploads = data / "uploads"
    uploads.mkdir(parents=True)

    monkeypatch.setattr("radar.config.DATA", data)
    monkeypatch.setattr("radar.config.ROOT", tmp_path)
    monkeypatch.setattr(up, "DATA", data)
    monkeypatch.setattr(up, "ROOT", tmp_path)
    monkeypatch.setattr(up, "PROFILE_PATH", data / "user_profile.json")
    monkeypatch.setattr(up, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(up, "RESUME_TEXT_CACHE", uploads / "resume_text.txt")
    monkeypatch.setattr(up, "UPLOAD_LOG_PATH", data / "upload_log.jsonl")
    return tmp_path


def test_empty_profile_not_ready(profile_env):
    save_profile({})
    assert is_profile_ready() is False
    block = build_candidate_block()
    assert "PROFILE EMPTY" in block
    assert "profile-empty" in block


def test_upload_and_links_build_candidate_block(profile_env):
    resume_src = profile_env / "my_resume.txt"
    resume_src.write_text(
        "Senior Vue developer with TypeScript experience.",
        encoding="utf-8",
    )

    upload_resume(resume_src)
    set_links(
        portfolio_url="https://example.com/portfolio/",
        github_url="https://github.com/testuser",
    )

    assert is_profile_ready() is True
    block = build_candidate_block()
    assert "Senior Vue developer" in block
    assert "https://example.com/portfolio/" in block
    assert "https://github.com/testuser" in block
    assert "point formulas" in block


def test_links_dict_reflects_profile(profile_env):
    resume_src = profile_env / "cv.txt"
    resume_src.write_text("Hello resume", encoding="utf-8")
    upload_resume(resume_src)
    set_links(portfolio_url="https://p.example/", github_url="https://gh.example/")

    links = links_dict()
    assert links["portfolioUrl"] == "https://p.example/"
    assert links["githubUrl"] == "https://gh.example/"
    assert links["resumePath"]
    assert Path(links["resumePath"]).is_file()


def test_via_cursor_payload_uses_profile_links(profile_env):
    resume_src = profile_env / "resume.txt"
    resume_src.write_text("Payload test resume line.", encoding="utf-8")
    upload_resume(resume_src)
    set_links(
        portfolio_url="https://portfolio.test/",
        github_url="https://github.com/payloadtest",
    )

    captured: dict = {}

    def fake_run(cmd, **kwargs):
        path = cmd[2]
        with open(path, encoding="utf-8") as f:
            captured.clear()
            captured.update(json.load(f))

        class R:
            stdout = json.dumps(
                {
                    "ok": True,
                    "score": 70,
                    "accept": True,
                    "reasons": ["ok"],
                    "elapsed_ms": 1,
                }
            )
            stderr = ""
            returncode = 0

        return R()

    with patch.object(cs, "_api_key", return_value="k"):
        with patch.object(cs, "subprocess") as sp:
            sp.run.side_effect = fake_run
            out = cs._via_cursor(
                title="Vue",
                company="Co",
                description="remote Vue3",
                salary="",
                schedule="remote",
                experience="",
                threshold=65,
                cfg={"cursor_model": "composer-2.5"},
            )

    assert out and out.get("ok")
    assert captured["portfolioUrl"] == "https://portfolio.test/"
    assert captured["githubUrl"] == "https://github.com/payloadtest"
    assert captured.get("resumePath")
    assert "Payload test resume line." in captured["candidateProfile"]
    assert "portfolio.test" in captured["candidateProfile"]
    assert "scoringRules" in captured
    assert load_scoring_context() in captured["scoringRules"]
