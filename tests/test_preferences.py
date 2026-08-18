# -*- coding: utf-8 -*-
"""Tests for user preference keyword buckets."""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from radar.preferences import (
    build_desirable_hh_url,
    hard_reject,
    normalize_keywords,
    save_preferences,
    search_seed_urls,
)


@pytest.fixture
def prefs_env(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    path = data / "preferences.json"
    monkeypatch.setattr("radar.config.DATA", data)
    monkeypatch.setattr("radar.preferences.DATA", data)
    monkeypatch.setattr("radar.preferences.PREFERENCES_PATH", path)
    return path


def test_normalize_keywords_strip_and_dedupe():
    assert normalize_keywords(["Vue", "vue", " Nuxt ", "", "Vue"]) == ["Vue", "Nuxt"]


def test_hard_reject_true_when_keyword_matches():
    prefs = {
        "desirable": [],
        "neutral": [],
        "undesirable": [],
        "reject": ["Angular"],
    }
    rejected, reasons = hard_reject(
        "Frontend Developer",
        "Must know Angular and RxJS",
        prefs=prefs,
    )
    assert rejected is True
    assert reasons == ["reject:Angular"]


def test_hard_reject_false_when_no_match():
    prefs = {
        "desirable": ["Vue"],
        "neutral": [],
        "undesirable": [],
        "reject": ["Angular"],
    }
    rejected, reasons = hard_reject(
        "Vue Developer",
        "Vue 3 TypeScript remote",
        prefs=prefs,
    )
    assert rejected is False
    assert reasons == []


def test_build_desirable_hh_url_sets_text_or_and_keeps_host():
    base = "https://hh.ru/search/vacancy?area=113&text=old"
    prefs = {
        "desirable": ["Vue", "Nuxt"],
        "neutral": [],
        "undesirable": [],
        "reject": [],
    }
    url = build_desirable_hh_url(base, prefs=prefs)
    assert url is not None
    parsed = urlparse(url)
    assert parsed.netloc == "hh.ru"
    assert parsed.path == "/search/vacancy"
    qs = parse_qs(parsed.query)
    assert qs["text"] == ["Vue OR Nuxt"]
    assert qs["area"] == ["113"]


def test_build_desirable_hh_url_none_when_desirable_empty():
    base = "https://hh.ru/search/vacancy?area=113"
    prefs = {
        "desirable": [],
        "neutral": [],
        "undesirable": [],
        "reject": [],
    }
    assert build_desirable_hh_url(base, prefs=prefs) is None


def test_search_seed_urls_returns_one_or_two(prefs_env):
    base = "https://hh.ru/search/vacancy?area=113"

    save_preferences(
        {
            "desirable": [],
            "neutral": [],
            "undesirable": [],
            "reject": [],
        }
    )
    assert search_seed_urls(base) == [base]

    save_preferences(
        {
            "desirable": ["Vue", "Nuxt"],
            "neutral": [],
            "undesirable": [],
            "reject": [],
        }
    )
    urls = search_seed_urls(base)
    assert len(urls) == 2
    assert urls[0] == base
    assert urls[1] != base
    assert "Vue+OR+Nuxt" in urls[1] or "Vue OR Nuxt" in urls[1]
