# -*- coding: utf-8 -*-
"""Cursor SDK vacancy scoring (+ rules fallback) and metrics log."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple

from .candidate_profile import build_candidate_block, links_dict, load_scoring_context
from .config import ROOT, load_config
from .cover_letter import _api_key
from .metrics_log import append_event
from .scorer import score_vacancy as score_vacancy_rules

BRIDGE = ROOT / "cursor_bridge" / "score_vacancy.mjs"
# Workspace root (parent of VacancyRadar); Cyrillic-safe via ROOT
RULES_CWD = ROOT.parent
METRICS_PATH = ROOT / "data" / "cursor_score_metrics.jsonl"


def scoring_mode(cfg: Optional[dict] = None) -> str:
    cfg = cfg or load_config()
    if bool(cfg.get("python_only", False)):
        return "rules"
    mode = str(cfg.get("scoring_mode") or "hybrid").strip().lower()
    return mode if mode in ("cursor", "rules", "hybrid") else "hybrid"


def _rules_score(
    *,
    title: str,
    snippet: str,
    salary_text: str,
    schedule: str,
    experience: str,
    cfg: dict,
) -> Tuple[int, List[str], bool]:
    threshold = int(cfg.get("score_threshold") or 70)
    floor = int(cfg.get("salary_floor") or 120000)
    good = int(cfg.get("salary_good") or 140000)
    return score_vacancy_rules(
        title,
        snippet,
        salary_text=salary_text,
        schedule=schedule,
        experience=experience,
        salary_floor=floor,
        salary_good=good,
        gate_threshold=threshold,
    )


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
    Returns (score, reasons, accept_ok, meta).
    meta: source, elapsed_ms, usage, fallback?
    """
    cfg = cfg or load_config()
    threshold = int(cfg.get("score_threshold") or 70)
    mode = scoring_mode(cfg)

    t0_rules = time.perf_counter()
    rules_score, rules_reasons, rules_ok = _rules_score(
        title=title,
        snippet=snippet,
        salary_text=salary_text,
        schedule=schedule,
        experience=experience,
        cfg=cfg,
    )
    rules_elapsed = int((time.perf_counter() - t0_rules) * 1000)

    if mode == "rules":
        meta = {"source": "rules", "elapsed_ms": rules_elapsed, "usage": None}
        _append_metric(
            {
                "ts": time.time(),
                "title": (title or "")[:120],
                "score": rules_score,
                "accept": rules_ok,
                "source": "rules",
                "elapsed_ms": rules_elapsed,
                "usage": None,
            }
        )
        return rules_score, rules_reasons, rules_ok, meta

    hybrid_min = int(cfg.get("hybrid_rules_min") or 60)
    if mode == "hybrid" and rules_score < hybrid_min:
        meta = {
            "source": "hybrid_prefilter",
            "elapsed_ms": rules_elapsed,
            "usage": None,
            "rules_score": rules_score,
        }
        reasons = list(rules_reasons) + [f"hybrid:prefilter<{hybrid_min}"]
        _append_metric(
            {
                "ts": time.time(),
                "title": (title or "")[:120],
                "score": rules_score,
                "accept": rules_ok,
                "source": "hybrid_prefilter",
                "elapsed_ms": rules_elapsed,
                "usage": None,
            }
        )
        return rules_score, reasons, rules_ok, meta

    if mode in ("cursor", "hybrid") and _api_key(cfg) and BRIDGE.exists():
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
            cursor_score = int(cur.get("score") or 0)
            score = max(cursor_score, rules_score) if mode == "hybrid" else cursor_score
            reasons = list(cur.get("reasons") or [])
            accept = bool(cur.get("accept"))
            accept_ok = accept or score >= threshold or (mode == "hybrid" and rules_ok)
            src = "hybrid_cursor" if mode == "hybrid" else "cursor"
            if mode == "hybrid":
                reasons = reasons + [f"rules:{rules_score}%"]
            meta = {
                "source": src,
                "elapsed_ms": int(cur.get("elapsed_ms") or 0) + rules_elapsed,
                "usage": cur.get("usage"),
                "runId": cur.get("runId"),
                "rules_score": rules_score,
            }
            _append_metric(
                {
                    "ts": time.time(),
                    "title": (title or "")[:120],
                    "score": score,
                    "accept": accept_ok,
                    "source": src,
                    "elapsed_ms": meta["elapsed_ms"],
                    "usage": meta["usage"],
                }
            )
            return score, reasons, accept_ok, meta

        if mode == "hybrid":
            meta = {
                "source": "hybrid_rules_fallback",
                "elapsed_ms": rules_elapsed
                + int((cur or {}).get("elapsed_ms") or 0)
                if isinstance(cur, dict)
                else rules_elapsed,
                "usage": None,
                "rules_score": rules_score,
            }
            reasons = list(rules_reasons) + ["hybrid:cursor-failed→rules"]
            if isinstance(cur, dict) and cur.get("error"):
                reasons.append(str(cur.get("error"))[:120])
            _append_metric(
                {
                    "ts": time.time(),
                    "title": (title or "")[:120],
                    "score": rules_score,
                    "accept": rules_ok,
                    "source": "hybrid_rules_fallback",
                    "elapsed_ms": meta["elapsed_ms"],
                    "usage": None,
                }
            )
            return rules_score, reasons, rules_ok, meta

        # Cursor-only mode: failure without rules fallback.
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

    if mode == "cursor" and not (_api_key(cfg) and BRIDGE.exists()):
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

    # hybrid without key/bridge → rules only
    meta = {"source": "rules", "elapsed_ms": rules_elapsed, "usage": None}
    _append_metric(
        {
            "ts": time.time(),
            "title": (title or "")[:120],
            "score": rules_score,
            "accept": rules_ok,
            "source": "rules",
            "elapsed_ms": rules_elapsed,
            "usage": None,
        }
    )
    return rules_score, rules_reasons, rules_ok, meta


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
