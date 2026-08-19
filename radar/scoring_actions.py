# -*- coding: utf-8 -*-
"""High-level Settings scoring Upload actions (profile / prefs / references / packs)."""
from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .config import load_config
from .preferences import load_preferences, save_preferences
from .profile_analyze import analyze_user_profile, calibrate_preferences
from .profile_packs import import_pack_from_path, list_packs, load_pack, save_pack
from .reference_calibrate import upload_references_and_calibrate
from .references import load_references
from .scoring_calibration import (
    load_calibration,
    merge_preferences_from_suggestion,
    save_calibration,
    write_calibration_md,
)
from .scoring_state import (
    fingerprint_preferences,
    fingerprint_profile,
    fingerprint_references,
    load_state,
    mark_preferences_synced,
    mark_profile_dirty,
    mark_profile_synced,
    mark_references_synced,
    ui_snapshot,
)
from .user_profile import (
    clear_profile,
    is_profile_ready,
    set_links,
    upload_resume,
)


def _write_b64_temp(filename: str, b64: str) -> Path:
    raw = base64.b64decode(b64)
    suffix = Path(filename or "resume.bin").suffix or ".bin"
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tf.write(raw)
    tf.close()
    return Path(tf.name)


def upload_profile_action(
    *,
    resume_b64: str = "",
    resume_filename: str = "",
    portfolio_url: str = "",
    github_url: str = "",
    activity_sphere: str = "",
    force: bool = False,
    cfg: Optional[dict] = None,
) -> Dict[str, Any]:
    """Save CV (+ optional links/sphere), run Cursor profile analysis, merge prefs."""
    cfg = cfg or load_config()
    st = load_state()

    if resume_b64:
        tmp = _write_b64_temp(resume_filename or "resume.bin", resume_b64)
        try:
            upload_resume(tmp, original_filename=resume_filename or "resume.bin")
        finally:
            try:
                tmp.unlink(missing_ok=True)  # type: ignore[arg-type]
            except TypeError:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
    elif not is_profile_ready():
        raise RuntimeError("No CV selected and no resume on disk")

    set_links(
        portfolio_url=str(portfolio_url or "").strip(),
        github_url=str(github_url or "").strip(),
        activity_sphere=str(activity_sphere or "").strip(),
    )

    # No-op if already synced and fingerprint unchanged
    if not force and st.get("profile_synced") and st.get("profile_fingerprint") == fingerprint_profile():
        return {"ok": True, "noop": True, "snapshot": ui_snapshot()}

    analysis = analyze_user_profile(cfg)
    suggested = analysis.get("suggested_preferences") or {}
    existing = load_preferences()
    merged = merge_preferences_from_suggestion(existing, suggested)
    save_preferences(merged)

    # Profile sync already marked inside analyze_user_profile; prefs changed → dirty until prefs Upload
    from .scoring_state import mark_preferences_dirty

    mark_preferences_dirty()
    # Keep profile synced after successful analysis
    mark_profile_synced()

    return {
        "ok": True,
        "noop": False,
        "suggested_preferences": suggested,
        "preferences": merged,
        "analysis": {
            "skills": analysis.get("skills") or [],
            "stack": analysis.get("stack") or [],
            "level": analysis.get("level") or "",
            "notes": analysis.get("notes") or "",
        },
        "snapshot": ui_snapshot(),
    }


def clear_profile_action() -> Dict[str, Any]:
    clear_profile()
    mark_profile_dirty()
    from .scoring_state import mark_preferences_dirty

    mark_preferences_dirty()
    return {"ok": True, "snapshot": ui_snapshot()}


def upload_preferences_action(
    prefs: Dict[str, List[str]],
    *,
    force: bool = False,
    cfg: Optional[dict] = None,
) -> Dict[str, Any]:
    cfg = cfg or load_config()
    cleaned = save_preferences(prefs or {})
    st = load_state()
    if (
        not force
        and st.get("preferences_synced")
        and st.get("preferences_fingerprint") == fingerprint_preferences()
    ):
        return {"ok": True, "noop": True, "snapshot": ui_snapshot()}

    calibrate_preferences(cfg)
    return {"ok": True, "noop": False, "preferences": cleaned, "snapshot": ui_snapshot()}


def upload_references_action(
    urls: Sequence[str],
    *,
    force: bool = False,
    cfg: Optional[dict] = None,
) -> Dict[str, Any]:
    cfg = cfg or load_config()
    url_list = [str(u).strip() for u in (urls or []) if str(u).strip()]
    if not url_list:
        raise RuntimeError("No reference URLs")

    st = load_state()
    # Pre-check noop against current disk + incoming set
    from .references import set_urls

    # If identical to disk and already synced — skip Cursor
    current = load_references().get("urls") or []
    if (
        not force
        and st.get("references_synced")
        and [u.lower() for u in current] == [u.lower() for u in url_list]
        and st.get("references_fingerprint") == fingerprint_references()
    ):
        return {"ok": True, "noop": True, "snapshot": ui_snapshot()}

    result = upload_references_and_calibrate(url_list, cfg)
    cal = load_calibration()
    cal["updated_at"] = cal.get("updated_at") or ""
    cal["source"] = "references_upload"
    cal["references_analysis"] = result if isinstance(result, dict) else {"raw": result}
    save_calibration(cal)
    write_calibration_md(cal)
    mark_references_synced()
    return {"ok": True, "noop": False, "calibration": result, "snapshot": ui_snapshot()}


def save_pack_action(name: str) -> Dict[str, Any]:
    pack = save_pack(name)
    return {"ok": True, "pack": pack, "snapshot": ui_snapshot(), "pack_names": list_packs()}


def load_pack_action(name: str) -> Dict[str, Any]:
    load_pack(name)
    return {"ok": True, "snapshot": ui_snapshot(), "pack_names": list_packs()}


def import_pack_action(path: str) -> Dict[str, Any]:
    import_pack_from_path(path)
    return {"ok": True, "snapshot": ui_snapshot(), "pack_names": list_packs()}


def import_pack_b64_action(filename: str, b64: str) -> Dict[str, Any]:
    tmp = _write_b64_temp(filename or "pack.json", b64)
    try:
        return import_pack_action(str(tmp))
    finally:
        try:
            tmp.unlink(missing_ok=True)  # type: ignore[arg-type]
        except TypeError:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
