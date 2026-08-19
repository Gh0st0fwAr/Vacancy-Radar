# -*- coding: utf-8 -*-
"""Tests for _with_search_period setting the search_period query param."""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from radar.search_hh import _with_search_period


def test_adds_search_period():
    url = "https://hh.ru/search/vacancy?text=Vue&area=113"
    result = _with_search_period(url, 7)
    parsed = urlparse(result)
    qs = parse_qs(parsed.query)
    assert qs["search_period"] == ["7"]
    assert qs["text"] == ["Vue"]
    assert qs["area"] == ["113"]


def test_replaces_existing_search_period():
    url = "https://hh.ru/search/vacancy?text=Vue&search_period=2"
    result = _with_search_period(url, 14)
    parsed = urlparse(result)
    qs = parse_qs(parsed.query)
    assert qs["search_period"] == ["14"]
    assert "text" in qs


def test_clamps_to_minimum_1():
    url = "https://hh.ru/search/vacancy?text=Vue"
    result = _with_search_period(url, 0)
    parsed = urlparse(result)
    qs = parse_qs(parsed.query)
    assert qs["search_period"] == ["1"]


def test_negative_days_clamped():
    url = "https://hh.ru/search/vacancy?text=Vue"
    result = _with_search_period(url, -5)
    parsed = urlparse(result)
    qs = parse_qs(parsed.query)
    assert qs["search_period"] == ["1"]


def test_preserves_other_params():
    url = "https://hh.ru/search/vacancy?text=Vue&schedule=remote&order_by=publication_time&items_on_page=50"
    result = _with_search_period(url, 3)
    parsed = urlparse(result)
    qs = parse_qs(parsed.query)
    assert qs["search_period"] == ["3"]
    assert qs["schedule"] == ["remote"]
    assert qs["order_by"] == ["publication_time"]
    assert qs["items_on_page"] == ["50"]
