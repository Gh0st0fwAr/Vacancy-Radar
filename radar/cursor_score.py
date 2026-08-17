# -*- coding: utf-8 -*-
"""Cursor SDK vacancy scoring and metrics log."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple

from .candidate_profile import build_candidate_block, links_dict, load_scoring_context
from .config import ROOT, load_config
from .cover_letter import _api_key
from .metrics_log import append_event

BRIDGE = ROOT / "cursor_bridge" / "score_vacancy.mjs"
RULES_CWD = ROOT.parent
METRICS_PATH = ROOT / "data" / "cursor_score_metrics.jsonl"


def score_for_search(
    *,
    title: str,
    snippet: str = "",
    salary_text: str = "",
    schedule: str = "",
    experience: str = "",
    company: str = "",
    cfg: Optional[dict] = None,
) -> Tuple[int, List[str], bool, Dict[str, Any]]:
    """
    Cursor-SDK-only scoring.
    Returns (score, reasons, accept_ok, meta).
    """
    cfg = cfg or load_config()
    threshold = int(cfg.get("score_threshold") or 70)

    if not (_api_key(cfg) and BRIDGE.exists()):
        meta = {"source": "cursor_unavailable", "elapsed_ms": 0, "usage": None}
        _append_metric(
            {
                "ts": time.time(),
                "title": (title or "")[:120],
                "score": 0,
                "accept": False,
                "source": "cursor_unavailable",
                "elapsed_ms": 0,
                "usage": None,
            }
        )
        return 0, ["cursor-unavailable"], False, meta

    cur = _via_cursor(
        title=title,
        company=company,
        description=snippet,
        salary=salary_text,
        schedule=schedule,
        experience=experience,
        threshold=threshold,
        cfg=cfg,
    )
    if cur and cur.get("ok"):
        score = int(cur.get("score") or 0)
        reasons = list(cur.get("reasons") or [])
        accept = bool(cur.get("accept"))
        accept_ok = accept and score >= threshold
        meta = {
            "source": "cursor",
            "elapsed_ms": int(cur.get("elapsed_ms") or 0),
            "usage": cur.get("usage"),
            "runId": cur.get("runId"),
        }
        _append_metric(
            {
                "ts": time.time(),
                "title": (title or "")[:120],
                "score": score,
                "accept": accept_ok,
                "source": "cursor",
                "elapsed_ms": meta["elapsed_ms"],
                "usage": meta["usage"],
            }
        )
        return score, reasons, accept_ok, meta

    meta = {
        "source": "cursor_failed",
        "elapsed_ms": int((cur or {}).get("elapsed_ms") or 0) if isinstance(cur, dict) else 0,
        "usage": None,
    }
    reasons = ["cursor-score-failed"]
    if isinstance(cur, dict) and cur.get("error"):
        reasons.append(str(cur.get("error"))[:120])
    _append_metric(
        {
            "ts": time.time(),
            "title": (title or "")[:120],
            "score": 0,
            "accept": False,
            "source": "cursor_failed",
            "elapsed_ms": meta["elapsed_ms"],
            "usage": None,
        }
    )
    return 0, reasons, False, meta


def _via_cursor(
    *,
    title: str,
    company: str,
    description: str,
    salary: str,
    schedule: str,
    experience: str,
    threshold: int,
    cfg: dict,
) -> Optional[dict]:
    key = _api_key(cfg)
    if not key or not BRIDGE.exists():
        return None
    links = links_dict()
    payload = {
        "title": title,
        "company": company,
        "description": description,
        "salary": salary,
        "schedule": schedule,
        "experience": experience,
        "threshold": threshold,
        "apiKey": key,
        "model": cfg.get("cursor_model") or "composer-2.5",
        "cwd": str(RULES_CWD),
        "candidateProfile": build_candidate_block(),
        "scoringRules": load_scoring_context(),
        "portfolioUrl": links["portfolioUrl"],
        "githubUrl": links["githubUrl"],
        "resumePath": links.get("resumePath") or "",
    }
    timeout = int(cfg.get("cursor_score_timeout_sec") or 120)
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", suffix=".json", delete=False
        ) as tf:
            json.dump(payload, tf, ensure_ascii=False)
            tmp = tf.name
        try:
            proc = subprocess.run(
                ["node", str(BRIDGE), tmp],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                cwd=str(BRIDGE.parent),
            )
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

        raw = (proc.stdout or "").strip()
        if not raw:
            return None
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        return data
    except Exception:
        return None


def _append_metric(row: dict) -> None:
    try:
        METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with METRICS_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass
    try:
        append_event(
            "score",
            ts=row.get("ts"),
            title=row.get("title"),
            score=row.get("score"),
            accept=row.get("accept"),
            source=row.get("source"),
            elapsed_ms=row.get("elapsed_ms"),
            usage=row.get("usage"),
        )
    except Exception:
        pass


def load_metrics(limit: int = 500) -> List[dict]:
    if not METRICS_PATH.exists():
        return []
    rows: List[dict] = []
    try:
        lines = METRICS_PATH.read_text(encoding="utf-8").splitlines()
        for line in lines[-limit:]:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    except Exception:
        return []
    return rows


def score_many_parallel(
    items: List[dict],
    *,
    cfg: Optional[dict] = None,
    workers: Optional[int] = None,
    on_progress: Optional[Callable[[str], None]] = None,
) -> List[dict]:
    """Score vacancies via a pool of node bridge processes."""
    if not items:
        return []
    cfg = cfg or load_config()
    n_workers = max(1, min(int(workers or cfg.get("cursor_score_workers") or 5), 6))

    def _one(idx: int, item: dict) -> tuple[int, dict]:
        sc, reasons, ok, meta = score_for_search(
            title=item.get("title") or "",
            snippet=item.get("snippet") or "",
            salary_text=item.get("salary") or "",
            schedule=item.get("schedule") or "",
            experience=item.get("experience") or "",
            company=item.get("company") or "",
            cfg=cfg,
        )
        out = dict(item)
        out.update(
            {
                "score": sc,
                "reasons": reasons,
                "accept_ok": ok,
                "score_meta": meta,
            }
        )
        return idx, out

    ordered: List[Optional[dict]] = [None] * len(items)
    done_n = 0
    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        futs = [pool.submit(_one, i, it) for i, it in enumerate(items)]
        for fut in as_completed(futs):
            idx, row = fut.result()
            ordered[idx] = row
            done_n += 1
            if on_progress:
                title = (row.get("title") or "")[:50]
                src = (row.get("score_meta") or {}).get("source") or "?"
                on_progress(f"  [{done_n}/{len(items)}] {title} → {row.get('score')}% ({src})")
    return [r for r in ordered if r is not None]
