# -*- coding: utf-8 -*-
"""Detect employer-side activity from HH stats snapshots."""
from __future__ import annotations

from typing import Any, Dict, List, Optional


# Metrics that mean "employer moved" for the applicant.
ACTIVITY_FIELDS = (
    ("invitations", "???????????"),
    ("interviews", "?????????????"),
    ("unread_messages", "????????? ? ????"),
)


def _as_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def detect_employer_activity(prev: Dict, new: Dict) -> List[Dict[str, Any]]:
    """
    Compare two stats snapshots.
    Returns events only when a watched counter *increases* and prev had a real value
    (avoids false alarm on first successful scrape).
    """
    prev = prev or {}
    new = new or {}
    if not new.get("ok"):
        return []
    events: List[Dict[str, Any]] = []
    for key, label in ACTIVITY_FIELDS:
        before = _as_int(prev.get(key))
        after = _as_int(new.get(key))
        if before is None or after is None:
            continue
        if after > before:
            events.append(
                {
                    "kind": key,
                    "label": label,
                    "from": before,
                    "to": after,
                    "delta": after - before,
                }
            )
    return events


def format_activity_toast(events: List[Dict[str, Any]]) -> str:
    if not events:
        return ""
    lines = [f"{e['label']}: {e['from']} ? {e['to']}" for e in events]
    return "\n".join(lines)
