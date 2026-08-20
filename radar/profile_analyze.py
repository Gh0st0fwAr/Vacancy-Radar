# -*- coding: utf-8 -*-
"""Cursor SDK analysis of uploaded candidate profile.

Calls cursor_bridge/analyze_profile.mjs to extract skills, stack, level,
and suggested preferences from the user's resume + links.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .config import DATA, ROOT, load_config
from .cover_letter import _api_key
from .scoring_calibration import (
    load_calibration,
    save_calibration,
    write_calibration_md,
)
from .scoring_state import mark_preferences_synced, mark_profile_synced
from .user_profile import (
    build_candidate_block,
    is_profile_ready,
    links_dict,
    load_resume_text,
)

logger = logging.getLogger("vacancyradar.profile_analyze")

BRIDGE = ROOT / "cursor_bridge" / "analyze_profile.mjs"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def analyze_user_profile(cfg: Optional[dict] = None) -> Dict[str, Any]:
    """Run Cursor analysis on the uploaded profile.

    Returns result dict including suggested_preferences.
    Raises if profile not ready or bridge missing.
    """
    if not is_profile_ready():
        raise RuntimeError("Profile not ready — upload a resume first")
    if not BRIDGE.exists():
        raise FileNotFoundError(f"Bridge not found: {BRIDGE}")

    cfg = cfg or load_config()
    key = _api_key(cfg)
    if not key:
        raise RuntimeError("cursor_api_key not configured")

    links = links_dict()
    candidate_block = build_candidate_block()
    resume_text = load_resume_text(max_chars=14000)

    payload = {
        "mode": "profile",
        "candidateProfile": candidate_block,
        "resumeText": resume_text,
        "portfolioUrl": links.get("portfolioUrl") or "",
        "githubUrl": links.get("githubUrl") or "",
        "apiKey": key,
        "model": cfg.get("cursor_model") or "composer-2.5",
        "cwd": str(ROOT.parent),
    }

    timeout = int(cfg.get("cursor_score_timeout_sec") or 120)
    # Binary mode avoids Windows text-mode \n→\r\n conversion that can
    # corrupt multi-byte UTF-8 sequences written by ensure_ascii=False.
    with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as tf:
        tf.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
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

    raw_out = (proc.stdout or "").strip()
    if proc.returncode != 0:
        err = (proc.stderr or "").strip()[:500]
        raise RuntimeError(f"analyze_profile.mjs failed (rc={proc.returncode}): {err}")

    try:
        result = json.loads(raw_out)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON from bridge: {exc}") from exc

    if not result.get("ok"):
        raise RuntimeError(result.get("error") or "Bridge returned ok=false")

    cal = load_calibration()
    cal["updated_at"] = _now_iso()
    cal["source"] = "profile_upload"
    cal["profile"] = {
        "skills": result.get("skills") or [],
        "stack": result.get("stack") or [],
        "level": result.get("level") or "",
        "notes": result.get("notes") or "",
        "suggested_preferences": result.get("suggested_preferences") or {},
    }
    if result.get("scoring_signals"):
        cal["scoring_signals"] = result["scoring_signals"]
    cal["raw_cursor"] = raw_out[:8000]
    save_calibration(cal)
    write_calibration_md(cal)
    mark_profile_synced()

    return result


def calibrate_preferences(cfg: Optional[dict] = None) -> Dict[str, Any]:
    """Light Cursor call acknowledging current preference buckets.

    Updates calibration.preferences_analysis section.
    """
    if not BRIDGE.exists():
        raise FileNotFoundError(f"Bridge not found: {BRIDGE}")

    cfg = cfg or load_config()
    key = _api_key(cfg)
    if not key:
        raise RuntimeError("cursor_api_key not configured")

    from .preferences import build_preferences_prompt_block, load_preferences

    prefs = load_preferences()
    prefs_block = build_preferences_prompt_block(prefs)

    candidate_block = ""
    if is_profile_ready():
        candidate_block = build_candidate_block()

    payload = {
        "mode": "preferences",
        "candidateProfile": candidate_block,
        "preferencesBlock": prefs_block,
        "apiKey": key,
        "model": cfg.get("cursor_model") or "composer-2.5",
        "cwd": str(ROOT.parent),
    }

    timeout = int(cfg.get("cursor_score_timeout_sec") or 120)
    with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as tf:
        tf.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
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

    raw_out = (proc.stdout or "").strip()
    if proc.returncode != 0:
        err = (proc.stderr or "").strip()[:500]
        raise RuntimeError(f"analyze_profile.mjs preferences failed (rc={proc.returncode}): {err}")

    try:
        result = json.loads(raw_out)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON from bridge: {exc}") from exc

    cal = load_calibration()
    cal["updated_at"] = _now_iso()
    cal["source"] = "preferences_upload"
    cal["preferences_analysis"] = {
        "notes": result.get("notes") or "",
        "buckets_echo": result.get("buckets_echo") or {},
    }
    cal["raw_cursor"] = raw_out[:8000]
    save_calibration(cal)
    write_calibration_md(cal)
    mark_preferences_synced()

    return {"ok": True, "preferences_analysis": cal["preferences_analysis"]}
