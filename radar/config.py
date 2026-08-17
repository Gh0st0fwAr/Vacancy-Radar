# -*- coding: utf-8 -*-
"""VacancyRadar paths and persistent config."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
ASSETS = ROOT / "assets"
CHROME_PROFILE = ROOT / "chrome_profile"
EXCLUDE_FILE = DATA / "_vacancy_exclude.json"
ROUNDS_GLOB = ROOT


def project_path(raw: str, fallback: Path | None = None) -> Path:
    """Resolve a config path against the project root (zip / other machine)."""
    s = (raw or "").strip()
    if not s:
        return fallback if fallback is not None else EXCLUDE_FILE
    p = Path(s)
    if p.is_absolute():
        return p
    return (ROOT / p).resolve()

DATA.mkdir(parents=True, exist_ok=True)
ASSETS.mkdir(parents=True, exist_ok=True)
CHROME_PROFILE.mkdir(parents=True, exist_ok=True)

CONFIG_PATH = DATA / "config.json"
QUEUE_PATH = DATA / "queue.json"
STATS_PATH = DATA / "stats.json"
SEEN_PATH = DATA / "seen.json"
NEGOTIATIONS_PATH = DATA / "negotiations.json"
LOG_PATH = DATA / "radar.log"

DEFAULT_CONFIG = {
    "search_interval_min": 15,
    "stats_interval_min": 15,
    "score_threshold": 70,
    "hotkey": "ctrl+alt+q",
    "sound_enabled": True,
    "dnd": False,
    "minimize_previous": False,
    "chrome_debug_port": 9222,
    "hh_search_url": (
        "https://hh.ru/search/vacancy?"
        "text=KEYWORD"
        "&search_field=name&search_field=description"
        "&schedule=remote"
        "&order_by=publication_time"
        "&search_period=2"
        "&items_on_page=50"
    ),
    "salary_target": 100000,
    "salary_floor": 60000,
    "salary_good": 80000,
    # Скоринг по полному тексту страницы вакансии (не по 800 символам карточки SERP).
    "deep_score": True,
    "vacancy_settle_sec": 1.1,
    "deep_score_max": 50,
    "serp_max_pages": 6,
    "clear_check_max_pages": 10,
    "hybrid_rules_min": 60,
    "exclude_manual_rounds": False,
    "clear_check_timeout_sec": 900,
    # Письма: на ветке pyrhon-only по умолчанию только локальный Python-шаблон.
    "cover_letter_via_cursor": False,
    "cursor_api_key": "",
    "cursor_model": "composer-2.5",
    "cover_letter_timeout_sec": 90,
    # python-only branch: rules + local letters. Cursor stays in code but is off.
    "scoring_mode": "rules",
    "python_only": True,
    "cursor_score_timeout_sec": 120,
    "cursor_score_workers": 5,
    "cursor_letter_workers": 5,
    # UI: 04 = hybrid default (see references/04_*.png)
    "ui_theme": "04",
    # Embedded WebEngine zoom (1.0 = CSS px as-is). Not a Chrome browser tab.
    "ui_zoom": 1.35,
    "autostart_enabled": False,
    "candidate_role": "",
    "resume_path": "data/nstyacv.pdf",
    "portfolio_url": "",
    "github_url": "",
    "telegram": "",
    "email": "",
    "experience_years_label": "",
    "candidate_pitch": "",
    "search_keywords": [],
    "exclude_keywords": [],
    "must_have_keywords": [],
    "nice_to_have_keywords": [],
    "hard_reject_keywords": [],
    "work_format_phrase": "Ищу удалённую работу",
    "cover_letter_closing": "",
    "require_remote": True,
    "skip_level_heuristic": False,
    "exclude_file": "data/_vacancy_exclude.json",
    "score_title": {},
    "score_body": {},
    "score_skills": {},
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
