# -*- coding: utf-8 -*-
"""Persistent scoring-sync state for Settings panels.

Tracks whether profile / preferences / references have been analyzed by Cursor
and whether the on-disk data still matches the last analyzed snapshot.
Storage: data/scoring_state.json
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import DATA, load_config, load_json, save_json

STATE_PATH = DATA / "scoring_state.json"

DEFAULT: Dict[str, Any] = {
    "profile_synced": False,
    "preferences_synced": False,
    "references_synced": False,
    "profile_analyzed_at": "",
    "preferences_analyzed_at": "",
    "references_analyzed_at": "",
    "profile_fingerprint": "",
    "preferences_fingerprint": "",
    "references_fingerprint": "",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_hash(*parts: str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
    return h.hexdigest()[:24]


# ---------------------------------------------------------------------------
# Load / Save
# ---------------------------------------------------------------------------

def load_state() -> Dict[str, Any]:
    raw = load_json(STATE_PATH, dict(DEFAULT))
    out = dict(DEFAULT)
    if isinstance(raw, dict):
        for k in DEFAULT:
            if k in raw:
                out[k] = raw[k]
    return out


def save_state(d: Dict[str, Any]) -> None:
    save_json(STATE_PATH, d)


# ---------------------------------------------------------------------------
# Fingerprints — deterministic hashes of source data
# ---------------------------------------------------------------------------

def fingerprint_profile() -> str:
    """Hash of resume_path + resume mtime/size + portfolio_url + github_url."""
    from .user_profile import load_profile, resolve_resume_path

    profile = load_profile()
    resume_path = resolve_resume_path(profile)
    parts = [
        profile.get("resume_path") or "",
        profile.get("portfolio_url") or "",
        profile.get("github_url") or "",
        profile.get("activity_sphere") or "",
    ]
    if resume_path and resume_path.is_file():
        st = resume_path.stat()
        parts.append(str(int(st.st_mtime)))
        parts.append(str(st.st_size))
    return _stable_hash(*parts)


def fingerprint_preferences() -> str:
    """Stable hash of 4 preference buckets."""
    from .preferences import BUCKETS, load_preferences

    prefs = load_preferences()
    parts: list[str] = []
    for b in BUCKETS:
        items = prefs.get(b) or []
        parts.append(f"{b}:" + ",".join(str(x).lower().strip() for x in items))
    return _stable_hash(*parts)


def fingerprint_references() -> str:
    """Stable hash of reference urls list."""
    from .references import load_references

    refs = load_references()
    urls = refs.get("urls") or []
    return _stable_hash(",".join(str(u).strip().lower() for u in urls))


# ---------------------------------------------------------------------------
# Mark synced / dirty
# ---------------------------------------------------------------------------

def mark_profile_synced() -> Dict[str, Any]:
    st = load_state()
    st["profile_synced"] = True
    st["profile_fingerprint"] = fingerprint_profile()
    st["profile_analyzed_at"] = _now_iso()
    save_state(st)
    return st


def mark_preferences_synced() -> Dict[str, Any]:
    st = load_state()
    st["preferences_synced"] = True
    st["preferences_fingerprint"] = fingerprint_preferences()
    st["preferences_analyzed_at"] = _now_iso()
    save_state(st)
    return st


def mark_references_synced() -> Dict[str, Any]:
    st = load_state()
    st["references_synced"] = True
    st["references_fingerprint"] = fingerprint_references()
    st["references_analyzed_at"] = _now_iso()
    save_state(st)
    return st


def mark_profile_dirty() -> Dict[str, Any]:
    st = load_state()
    st["profile_synced"] = False
    save_state(st)
    return st


def mark_preferences_dirty() -> Dict[str, Any]:
    st = load_state()
    st["preferences_synced"] = False
    save_state(st)
    return st


def mark_references_dirty() -> Dict[str, Any]:
    st = load_state()
    st["references_synced"] = False
    save_state(st)
    return st


# ---------------------------------------------------------------------------
# Recompute sync flags on hydrate
# ---------------------------------------------------------------------------

def recompute_sync_flags() -> Dict[str, Any]:
    """Compare fingerprints to disk vs stored; if mismatch set synced False.

    If profile ready and fingerprints match, keep True. Call this on hydrate.
    """
    st = load_state()

    current_pf = fingerprint_profile()
    if st.get("profile_fingerprint") and st["profile_fingerprint"] != current_pf:
        st["profile_synced"] = False

    current_prefs = fingerprint_preferences()
    if st.get("preferences_fingerprint") and st["preferences_fingerprint"] != current_prefs:
        st["preferences_synced"] = False

    current_refs = fingerprint_references()
    if st.get("references_fingerprint") and st["references_fingerprint"] != current_refs:
        st["references_synced"] = False

    save_state(st)
    return st


# ---------------------------------------------------------------------------
# UI snapshot for frontend
# ---------------------------------------------------------------------------

def ui_snapshot() -> Dict[str, Any]:
    """Dict for frontend: synced flags + profile fields + preferences buckets
    + references urls + pack names + clear_check_days + calibration_summary."""
    st = recompute_sync_flags()

    from .user_profile import is_profile_ready, load_profile, resolve_resume_path
    profile = load_profile()
    resume_path = resolve_resume_path(profile)

    from .preferences import load_preferences
    prefs = load_preferences()

    from .references import load_references
    refs = load_references()

    cfg = load_config()

    pack_names: List[str] = []
    try:
        from .profile_packs import list_packs
        pack_names = list_packs()
    except Exception:
        pass

    calibration_summary = ""
    try:
        from .scoring_calibration import load_calibration
        cal = load_calibration()
        if cal.get("profile", {}).get("notes"):
            calibration_summary = str(cal["profile"]["notes"])[:200]
        elif cal.get("updated_at"):
            calibration_summary = f"Last calibration: {cal['updated_at']}"
    except Exception:
        pass

    return {
        "profile_synced": bool(st.get("profile_synced")),
        "preferences_synced": bool(st.get("preferences_synced")),
        "references_synced": bool(st.get("references_synced")),
        "profile_analyzed_at": st.get("profile_analyzed_at") or "",
        "preferences_analyzed_at": st.get("preferences_analyzed_at") or "",
        "references_analyzed_at": st.get("references_analyzed_at") or "",
        "profile": {
            "filename": profile.get("resume_filename") or "",
            "portfolio": profile.get("portfolio_url") or "",
            "github": profile.get("github_url") or "",
            "activity_sphere": profile.get("activity_sphere") or "",
            "ready": is_profile_ready(),
        },
        "preferences": prefs,
        "references_urls": refs.get("urls") or [],
        "pack_names": pack_names,
        "clear_check_days": int(cfg.get("clear_check_days") or 7),
        "calibration_summary": calibration_summary,
    }
