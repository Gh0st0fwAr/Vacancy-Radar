# -*- coding: utf-8 -*-
"""Scoring calibration artifacts from Cursor analysis of profile / preferences / references.

Storage:
- data/scoring_calibration.json  (machine-readable)
- data/scoring_calibration.md    (human/Cursor-agent readable)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import DATA, load_json, save_json

CALIBRATION_JSON = DATA / "scoring_calibration.json"
CALIBRATION_MD = DATA / "scoring_calibration.md"

DEFAULT_CALIBRATION: Dict[str, Any] = {
    "updated_at": "",
    "source": "",
    "profile": {
        "skills": [],
        "stack": [],
        "level": "",
        "notes": "",
        "suggested_preferences": {
            "desirable": [],
            "neutral": [],
            "undesirable": [],
            "reject": [],
        },
    },
    "preferences_analysis": {"notes": "", "buckets_echo": {}},
    "references_analysis": {},
    "raw_cursor": "",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_calibration() -> Dict[str, Any]:
    raw = load_json(CALIBRATION_JSON, dict(DEFAULT_CALIBRATION))
    if not isinstance(raw, dict):
        return dict(DEFAULT_CALIBRATION)
    return raw


def save_calibration(data: Dict[str, Any]) -> None:
    save_json(CALIBRATION_JSON, data)


# ---------------------------------------------------------------------------
# Human-readable markdown composition
# ---------------------------------------------------------------------------

def write_calibration_md(data: Dict[str, Any]) -> None:
    """Write human-readable markdown for later Cursor-agent reading."""
    lines: List[str] = ["# Scoring Calibration", ""]

    updated = data.get("updated_at") or ""
    source = data.get("source") or ""
    if updated:
        lines.append(f"Updated: {updated}")
    if source:
        lines.append(f"Source: {source}")
    lines.append("")

    profile = data.get("profile") or {}
    if profile:
        lines.append("## Profile Analysis")
        if profile.get("level"):
            lines.append(f"- Level: {profile['level']}")
        if profile.get("skills"):
            lines.append(f"- Skills: {', '.join(str(s) for s in profile['skills'])}")
        if profile.get("stack"):
            lines.append(f"- Stack: {', '.join(str(s) for s in profile['stack'])}")
        if profile.get("notes"):
            lines.append(f"- Notes: {profile['notes']}")
        sp = profile.get("suggested_preferences") or {}
        if any(sp.get(b) for b in ("desirable", "neutral", "undesirable", "reject")):
            lines.append("")
            lines.append("### Suggested Preferences")
            for bucket in ("desirable", "neutral", "undesirable", "reject"):
                items = sp.get(bucket) or []
                if items:
                    lines.append(f"- {bucket}: {', '.join(str(x) for x in items)}")
        lines.append("")

    pref_a = data.get("preferences_analysis") or {}
    if pref_a.get("notes") or pref_a.get("buckets_echo"):
        lines.append("## Preferences Analysis")
        if pref_a.get("notes"):
            lines.append(pref_a["notes"])
        echo = pref_a.get("buckets_echo") or {}
        if echo:
            for bucket, items in echo.items():
                if items:
                    lines.append(f"- {bucket}: {', '.join(str(x) for x in items)}")
        lines.append("")

    refs_a = data.get("references_analysis") or {}
    if refs_a:
        lines.append("## References Analysis")
        lines.append(json.dumps(refs_a, ensure_ascii=False, indent=2))
        lines.append("")

    raw = data.get("raw_cursor") or ""
    if raw:
        lines.append("## Raw Cursor Output")
        lines.append(f"```\n{raw[:6000]}\n```")
        lines.append("")

    CALIBRATION_MD.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Merge preferences from suggestion (intersection rule)
# ---------------------------------------------------------------------------

def merge_preferences_from_suggestion(
    existing_prefs: Dict[str, List[str]],
    suggested: Dict[str, List[str]],
) -> Dict[str, List[str]]:
    """Merge Cursor-suggested keywords into preference buckets.

    Rules (stable — do not wipe user/Cursor keywords on re-upload):
    - If existing bucket is empty → use suggested as-is (first fill).
    - Else → **union**: keep all existing tags, append new suggested ones
      (case-insensitive dedupe, existing casing wins).
    """
    buckets = ("desirable", "neutral", "undesirable", "reject")
    result: Dict[str, List[str]] = {}
    for bucket in buckets:
        existing = list(existing_prefs.get(bucket) or [])
        sugg = list(suggested.get(bucket) or [])
        if not existing:
            result[bucket] = sugg
            continue
        seen = {str(x).lower().strip() for x in existing}
        merged = list(existing)
        for x in sugg:
            key = str(x).lower().strip()
            if key and key not in seen:
                seen.add(key)
                merged.append(x)
        result[bucket] = merged
    return result
