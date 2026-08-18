# -*- coding: utf-8 -*-
"""Backward-compatible imports for candidate scoring context.

Prefer ``radar.user_profile`` for new code. This module re-exports the
user-profile API and keeps ``load_scoring_context`` for Cursor SDK callers.
"""
from __future__ import annotations

from .config import ROOT
from .user_profile import (  # noqa: F401
    EMPTY_PROFILE,
    PROFILE_PATH,
    RESUME_TEXT_CACHE,
    UPLOADS_DIR,
    build_candidate_block,
    clear_profile,
    is_profile_ready,
    links_dict,
    load_profile,
    load_resume_text,
    resolve_resume_path,
    save_profile,
    set_links,
    upload_resume,
)

SCORING_CONTEXT_PATH = ROOT / "cursor_bridge" / "SCORING_CONTEXT.md"


def load_scoring_context() -> str:
    """Compose SDK rubric: base MD + preference buckets + reference calibration."""
    parts: list[str] = []
    if SCORING_CONTEXT_PATH.exists():
        try:
            base = SCORING_CONTEXT_PATH.read_text(encoding="utf-8").strip()
            if base:
                parts.append(base)
        except OSError:
            pass
    if not parts:
        links = links_dict()
        portfolio = links.get("portfolioUrl") or "(not set)"
        github = links.get("githubUrl") or "(not set)"
        parts.append(
            f"Resume: user-uploaded profile. Portfolio: {portfolio}. GitHub: {github}. "
            "Judge FIT from candidate block + vacancy text; no Python point formulas."
        )
    try:
        from .preferences import build_preferences_prompt_block

        pref = build_preferences_prompt_block()
        if pref:
            parts.append(pref)
    except Exception:
        pass
    try:
        from .references import build_references_prompt_block

        refs = build_references_prompt_block()
        if refs:
            parts.append(refs)
    except Exception:
        pass
    return "\n\n".join(parts).strip()
