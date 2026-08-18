# -*- coding: utf-8 -*-
"""User preference keyword buckets for scoring / hard-reject gates."""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .config import DATA, load_json, save_json

PREFERENCES_PATH = DATA / "preferences.json"
UPLOAD_LOG_PATH = DATA / "upload_log.jsonl"

BUCKETS: Tuple[str, ...] = ("desirable", "neutral", "undesirable", "reject")

DEFAULT_PREFERENCES: Dict[str, List[str]] = {
    "desirable": [],
    "neutral": [],
    "undesirable": [],
    "reject": [],
}


def normalize_keywords(items: Optional[Iterable[Any]]) -> List[str]:
    """Strip, drop empties, dedupe case-insensitively (keep first casing)."""
    out: List[str] = []
    seen: set[str] = set()
    if not items:
        return out
    for raw in items:
        kw = str(raw or "").strip()
        if not kw:
            continue
        key = kw.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(kw)
    return out


def _coerce_preferences(raw: Any) -> Dict[str, List[str]]:
    data = dict(DEFAULT_PREFERENCES)
    if not isinstance(raw, dict):
        return data
    for name in BUCKETS:
        data[name] = normalize_keywords(raw.get(name) or [])
    return data


def load_preferences() -> Dict[str, List[str]]:
    return _coerce_preferences(load_json(PREFERENCES_PATH, dict(DEFAULT_PREFERENCES)))


def save_preferences(data: Dict[str, Any]) -> Dict[str, List[str]]:
    cleaned = _coerce_preferences(data)
    save_json(PREFERENCES_PATH, cleaned)
    return cleaned


def set_bucket(name: str, items: Sequence[Any]) -> Dict[str, List[str]]:
    name = str(name or "").strip().lower()
    if name not in BUCKETS:
        raise ValueError(f"Unknown preference bucket: {name!r}")
    data = load_preferences()
    data[name] = normalize_keywords(items)
    return save_preferences(data)


def add_keyword(bucket: str, kw: str) -> Dict[str, List[str]]:
    bucket = str(bucket or "").strip().lower()
    if bucket not in BUCKETS:
        raise ValueError(f"Unknown preference bucket: {bucket!r}")
    data = load_preferences()
    data[bucket] = normalize_keywords([*(data.get(bucket) or []), kw])
    return save_preferences(data)


def remove_keyword(bucket: str, kw: str) -> Dict[str, List[str]]:
    bucket = str(bucket or "").strip().lower()
    if bucket not in BUCKETS:
        raise ValueError(f"Unknown preference bucket: {bucket!r}")
    target = str(kw or "").strip().lower()
    data = load_preferences()
    data[bucket] = [
        x for x in (data.get(bucket) or []) if str(x).strip().lower() != target
    ]
    return save_preferences(data)


def match_bucket(bucket_items: Sequence[Any], text: str) -> List[str]:
    """Return keywords from bucket_items that appear as substrings in text (ci)."""
    haystack = str(text or "").lower()
    matched: List[str] = []
    for raw in bucket_items or []:
        kw = str(raw or "").strip()
        if not kw:
            continue
        if kw.lower() in haystack:
            matched.append(kw)
    return matched


def _haystack(
    title: str,
    snippet: str,
    schedule: str = "",
    experience: str = "",
) -> str:
    return " ".join(
        str(p or "") for p in (title, snippet, schedule, experience)
    )


def match_reject(
    title: str,
    snippet: str,
    schedule: str = "",
    experience: str = "",
    prefs: Optional[Dict[str, List[str]]] = None,
) -> List[str]:
    data = prefs if prefs is not None else load_preferences()
    return match_bucket(data.get("reject") or [], _haystack(title, snippet, schedule, experience))


def classify_hits(
    title: str,
    snippet: str,
    schedule: str = "",
    experience: str = "",
    prefs: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, List[str]]:
    data = prefs if prefs is not None else load_preferences()
    text = _haystack(title, snippet, schedule, experience)
    return {
        name: match_bucket(data.get(name) or [], text) for name in BUCKETS
    }


def hard_reject(
    title: str,
    snippet: str,
    schedule: str = "",
    experience: str = "",
    prefs: Optional[Dict[str, List[str]]] = None,
) -> Tuple[bool, List[str]]:
    hits = match_reject(title, snippet, schedule, experience, prefs=prefs)
    if not hits:
        return False, []
    reasons = [f"reject:{kw}" for kw in hits]
    return True, reasons


def build_preferences_prompt_block(prefs: Optional[Dict[str, List[str]]] = None) -> str:
    """Text block for Cursor SDK describing preference buckets and scoring rules."""
    data = prefs if prefs is not None else load_preferences()

    def _fmt(name: str) -> str:
        items = data.get(name) or []
        if not items:
            return "(none)"
        return ", ".join(str(x) for x in items)

    return (
        "## User preference keywords (must follow)\n"
        "Four buckets control how vacancy text is interpreted:\n"
        "- **Desirable** — boosts FIT when present in the vacancy.\n"
        "- **Neutral** — note presence; neither boosts nor lowers FIT.\n"
        "- **Undesirable** — lowers FIT when present.\n"
        "- **Reject** — hard rule: MUST reject the vacancy if any reject keyword matches "
        "(do not score as fit; treat as automatic no).\n"
        "\n"
        f"Desirable: {_fmt('desirable')}\n"
        f"Neutral: {_fmt('neutral')}\n"
        f"Undesirable: {_fmt('undesirable')}\n"
        f"Reject: {_fmt('reject')}\n"
    ).strip()


def append_upload_log(kind: str, message: str, **extra: Any) -> None:
    """Append one line to data/upload_log.jsonl."""
    row: Dict[str, Any] = {
        "ts": time.time(),
        "at": datetime.now(timezone.utc).isoformat(),
        "kind": str(kind or ""),
        "message": str(message or ""),
    }
    for k, v in extra.items():
        if v is not None:
            row[k] = v
    try:
        UPLOAD_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with UPLOAD_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def build_desirable_hh_url(
    base_hh_url: str,
    prefs: Optional[Dict[str, List[str]]] = None,
) -> Optional[str]:
    """Clone hh_search_url but set text= to OR of Desirable keywords.

    Returns None if Desirable is empty. Title matches on Desirable words are
    intentional (e.g. Senior in Desirable pulls Senior vacancies for scoring).
    """
    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

    data = prefs if prefs is not None else load_preferences()
    kws = normalize_keywords(data.get("desirable") or [])
    if not kws:
        return None
    base = str(base_hh_url or "").strip()
    if not base:
        return None
    # Cap OR-query size for HH
    kws = kws[:24]
    text = " OR ".join(kws)
    parsed = urlparse(base)
    pairs = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k != "text"]
    pairs.append(("text", text))
    fields = [v for k, v in pairs if k == "search_field"]
    if "name" not in fields:
        pairs.append(("search_field", "name"))
    if "description" not in fields:
        pairs.append(("search_field", "description"))
    return urlunparse(parsed._replace(query=urlencode(pairs, doseq=True)))


def search_seed_urls(base_hh_url: str) -> List[str]:
    """Base HH URL plus optional Desirable-derived URL (deduped)."""
    urls: List[str] = []
    base = str(base_hh_url or "").strip()
    if base:
        urls.append(base)
    extra = build_desirable_hh_url(base)
    if extra and extra not in urls:
        urls.append(extra)
    return urls
