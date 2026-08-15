# -*- coding: utf-8 -*-
"""VacancyRadar paths and persistent config."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ASSETS = ROOT / "assets"
CHROME_PROFILE = ROOT / "chrome_profile"
EXCLUDE_FILE = Path(r"G:\Лёха уроки\_vacancy_exclude.json")
ROUNDS_GLOB = Path(r"G:\Лёха уроки")

DATA.mkdir(parents=True, exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)
CHROME_PROFILE.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = DATA / "config.json"
QUEUE_PATH = DATA / "queue.json"
STATS_PATH = DATA / "stats.json"
SEEN_PATH = DATA / "seen.json"
LOG_PATH = DATA / "radar.log"

DEFAULT_CONFIG = {
    "search_interval_min": 15,
    "stats_interval_min": 30,
    "score_threshold": 70,
    "hotkey": "ctrl+alt+q",
    "sound_enabled": True,
    "dnd": False,
    "minimize_previous": False,
    "chrome_debug_port": 9222,
    "hh_search_url": (
        "https://hh.ru/search/vacancy?"
        "text=Vue+OR+Nuxt"
        "&search_field=name&search_field=description"
        "&schedule=remote"
        "&order_by=publication_time"
        "&search_period=1"
        "&items_on_page=50"
    ),
    "salary_target": 160000,
    "salary_floor": 120000,
    # Скоринг по полному тексту страницы вакансии (не по 800 символам карточки SERP).
    "deep_score": True,
    "vacancy_settle_sec": 1.1,
    "deep_score_max": 50,
    # Письма через Cursor SDK (Node bridge). Без ключа — локальная адаптация под текст.
    "cover_letter_via_cursor": True,
    "cursor_api_key": "",
    "cursor_model": "composer-2.5",
    "cover_letter_timeout_sec": 90,
}


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(load_json(CONFIG_PATH, {}))
    return cfg


def save_config(cfg: dict) -> None:
    save_json(CONFIG_PATH, cfg)
