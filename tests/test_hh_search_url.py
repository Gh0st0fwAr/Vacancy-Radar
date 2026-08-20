# -*- coding: utf-8 -*-
"""Tests for dynamic hh.ru search URL building."""
from __future__ import annotations

import json

import pytest
from urllib.parse import parse_qs, unquote, urlparse

from radar.config import save_json
from radar.hh_search_url import (
    NEUTRAL_HH_SEARCH_URL,
    build_hh_search_url,
    sphere_seed_keywords,
    sync_hh_search_url_to_config,
)
from radar.preferences import save_preferences


@pytest.fixture
def hh_env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    config_path = data / "config.json"
    profile_path = data / "user_profile.json"
    prefs_path = data / "preferences.json"

    monkeypatch.setattr("radar.config.DATA", data)
    monkeypatch.setattr("radar.config.CONFIG_PATH", config_path)
    monkeypatch.setattr("radar.user_profile.DATA", data)
    monkeypatch.setattr("radar.user_profile.PROFILE_PATH", profile_path)
    monkeypatch.setattr("radar.preferences.DATA", data)
    monkeypatch.setattr("radar.preferences.PREFERENCES_PATH", prefs_path)

    return {
        "data": data,
        "config_path": config_path,
        "profile_path": profile_path,
        "prefs_path": prefs_path,
    }


def _text_param(url: str) -> str:
    qs = parse_qs(urlparse(url).query)
    return unquote(qs.get("text", [""])[0])


def test_sphere_seed_keywords_designer():
    seeds = sphere_seed_keywords("Дизайнер")
    assert "дизайнер" in seeds
    assert "designer" in seeds


def test_build_hh_search_url_designer_sphere():
    url = build_hh_search_url(sphere="Дизайнер")
    text = _text_param(url).lower()
    assert "дизайнер" in text or "designer" in text
    qs = parse_qs(urlparse(url).query)
    assert qs.get("schedule") == ["remote"]


def test_build_hh_search_url_desirable_vue():
    url = build_hh_search_url(desirable=["Vue", "Nuxt", "TypeScript"])
    text = _text_param(url)
    assert "Vue" in text
    assert "Nuxt" in text


def test_build_hh_search_url_empty_is_neutral():
    url = build_hh_search_url()
    qs = parse_qs(urlparse(url).query)
    assert "text" not in qs
    assert qs.get("schedule") == ["remote"]
    assert qs.get("search_field") == ["name", "description"]
    assert url.startswith("https://hh.ru/search/vacancy")


def test_neutral_template_has_no_vue():
    assert "Vue" not in NEUTRAL_HH_SEARCH_URL


def test_build_hh_search_url_desirable_arg_ignores_sphere():
    """Explicit desirable= is for secondary SERP; sphere is ignored in that path."""
    url = build_hh_search_url(sphere="Дизайнер", desirable=["Vue"])
    assert "Vue" in _text_param(url)
    assert "дизайнер" not in _text_param(url).lower()


def test_sync_primary_url_uses_sphere_not_desirable(hh_env):
    cfg = {
        "cursor_api_key": "secret-key-123",
        "score_threshold": 77,
        "hh_search_url": NEUTRAL_HH_SEARCH_URL,
    }
    save_json(hh_env["config_path"], cfg)

    save_json(
        hh_env["profile_path"],
        {"activity_sphere": "Дизайнер", "resume_path": "", "updated_at": ""},
    )
    save_preferences(
        {
            "desirable": ["Figma", "инфографика", "Vue"],
            "neutral": [],
            "undesirable": [],
            "reject": [],
        }
    )

    url = sync_hh_search_url_to_config()
    saved = json.loads(hh_env["config_path"].read_text(encoding="utf-8"))
    text = _text_param(url).lower()

    assert saved["cursor_api_key"] == "secret-key-123"
    assert saved["score_threshold"] == 77
    assert saved["hh_search_url"] == url
    assert "дизайнер" in text or "designer" in text
    assert "Vue" not in _text_param(url)
    assert "Figma" not in _text_param(url)


def test_sync_falls_back_to_neutral_without_sphere(hh_env):
    save_json(
        hh_env["config_path"],
        {"cursor_api_key": "k", "hh_search_url": NEUTRAL_HH_SEARCH_URL},
    )
    save_json(
        hh_env["profile_path"],
        {"activity_sphere": "", "resume_path": "", "updated_at": ""},
    )
    save_preferences(
        {
            "desirable": ["Vue"],
            "neutral": [],
            "undesirable": [],
            "reject": [],
        }
    )

    url = sync_hh_search_url_to_config()
    qs = parse_qs(urlparse(url).query)
    assert "text" not in qs or not qs.get("text", [""])[0]
