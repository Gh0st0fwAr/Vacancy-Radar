# -*- coding: utf-8 -*-
"""Unified append-only metrics for VacancyRadar (search / score / letter).

Passive consumers (stats watcher) read this file. Writing here never calls Cursor.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .config import DATA

METRICS_PATH = DATA / "radar_metrics.jsonl"


def append_event(kind: str, **fields: Any) -> None:
    """Append one metric event. kind: search | score | letter."""
    row: Dict[str, Any] = {"kind": str(kind)}
    for k, v in fields.items():
        if v is not None:
            row[k] = v
    if "ts" not in row:
        row["ts"] = time.time()
    try:
        METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with METRICS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _usage_tokens(usage: Any) -> Dict[str, Optional[int]]:
    if not isinstance(usage, dict):
        return {"inputTokens": None, "outputTokens": None, "totalTokens": None}
    inp = usage.get("inputTokens")
    out = usage.get("outputTokens")
    tot = usage.get("totalTokens")
    if tot is None and (inp is not None or out is not None):
        tot = int(inp or 0) + int(out or 0)
    return {
        "inputTokens": int(inp) if inp is not None else None,
        "outputTokens": int(out) if out is not None else None,
        "totalTokens": int(tot) if tot is not None else None,
    }


def flatten_usage(row: dict) -> dict:
    u = _usage_tokens(row.get("usage"))
    out = dict(row)
    out.update(u)
    return out


def read_events(
    path: Path = METRICS_PATH,
    *,
    since_ts: Optional[float] = None,
    kinds: Optional[Iterable[str]] = None,
    limit: Optional[int] = None,
) -> List[dict]:
    if not path.exists():
        return []
    kind_set = set(kinds) if kinds else None
    rows: List[dict] = []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if limit is not None:
            lines = lines[-limit:]
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            ts = float(row.get("ts") or 0)
            if since_ts is not None and ts < since_ts:
                continue
            if kind_set is not None and str(row.get("kind") or "") not in kind_set:
                continue
            rows.append(flatten_usage(row))
    except Exception:
        return []
    return rows


def read_legacy_score_events(
    path: Path,
    *,
    since_ts: Optional[float] = None,
) -> List[dict]:
    """Adapt cursor_score_metrics.jsonl (no kind field) into score events."""
    if not path.exists():
        return []
    rows: List[dict] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            ts = float(row.get("ts") or 0)
            if since_ts is not None and ts < since_ts:
                continue
            adapted = {
                "ts": ts,
                "kind": "score",
                "title": row.get("title"),
                "score": row.get("score"),
                "accept": row.get("accept"),
                "source": row.get("source"),
                "elapsed_ms": row.get("elapsed_ms"),
                "usage": row.get("usage"),
                "legacy": True,
            }
            rows.append(flatten_usage(adapted))
    except Exception:
        return []
    return rows
