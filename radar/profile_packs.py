# -*- coding: utf-8 -*-
"""Named profile packs: save / load / import / export entire profile snapshots.

Storage: data/profile_packs/index.json + {name}.json per pack.
Resume files are embedded as base64 for portability.
"""
from __future__ import annotations

import base64
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .config import DATA, load_json, save_json

PACKS_DIR = DATA / "profile_packs"
INDEX_PATH = PACKS_DIR / "index.json"

DEFAULT_INDEX: Dict[str, Any] = {"names": [], "active": ""}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_name(name: str) -> str:
    s = str(name or "").strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^\w\-]", "", s, flags=re.UNICODE)
    s = s.strip("_- ")[:64]
    return s or "pack"


def _ensure_dir() -> Path:
    PACKS_DIR.mkdir(parents=True, exist_ok=True)
    return PACKS_DIR


def _load_index() -> Dict[str, Any]:
    raw = load_json(INDEX_PATH, dict(DEFAULT_INDEX))
    if not isinstance(raw, dict):
        return dict(DEFAULT_INDEX)
    return {
        "names": list(raw.get("names") or []),
        "active": str(raw.get("active") or ""),
    }


def _save_index(idx: Dict[str, Any]) -> None:
    _ensure_dir()
    save_json(INDEX_PATH, idx)


def _pack_path(name: str) -> Path:
    return PACKS_DIR / f"{_sanitize_name(name)}.json"


def _read_file_base64(path: Path) -> str:
    if not path.is_file():
        return ""
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _write_file_base64(dest: Path, b64: str) -> None:
    if not b64:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(base64.b64decode(b64))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_packs() -> List[str]:
    idx = _load_index()
    return list(idx.get("names") or [])


def save_pack(name: str) -> Dict[str, Any]:
    """Snapshot current profile/prefs/refs/calibration/state into a named pack."""
    from .preferences import load_preferences
    from .references import load_references
    from .scoring_calibration import load_calibration
    from .scoring_state import load_state
    from .user_profile import load_profile, resolve_resume_path

    safe = _sanitize_name(name)
    _ensure_dir()

    profile = load_profile()
    resume_path = resolve_resume_path(profile)
    resume_b64 = ""
    resume_filename = profile.get("resume_filename") or ""
    if resume_path and resume_path.is_file():
        resume_b64 = _read_file_base64(resume_path)
        if not resume_filename:
            resume_filename = resume_path.name

    pack_data = {
        "name": safe,
        "created_at": _now_iso(),
        "user_profile": profile,
        "resume_base64": resume_b64,
        "resume_filename": resume_filename,
        "preferences": load_preferences(),
        "references": load_references(),
        "scoring_state": load_state(),
        "scoring_calibration": load_calibration(),
    }

    save_json(_pack_path(safe), pack_data)

    idx = _load_index()
    names = list(idx.get("names") or [])
    if safe not in names:
        names.append(safe)
    idx["names"] = names
    idx["active"] = safe
    _save_index(idx)

    return {"ok": True, "name": safe, "path": str(_pack_path(safe))}


def load_pack(name: str) -> Dict[str, Any]:
    """Restore a named pack into live data files."""
    from .preferences import save_preferences
    from .references import save_references
    from .scoring_calibration import save_calibration, write_calibration_md
    from .scoring_state import save_state
    from .user_profile import UPLOADS_DIR, save_profile

    safe = _sanitize_name(name)
    pack_file = _pack_path(safe)
    if not pack_file.is_file():
        raise FileNotFoundError(f"Pack not found: {safe}")

    pack = load_json(pack_file, {})
    if not isinstance(pack, dict):
        raise ValueError("Invalid pack file")

    if pack.get("user_profile"):
        profile = dict(pack["user_profile"])
        resume_b64 = pack.get("resume_base64") or ""
        resume_fn = pack.get("resume_filename") or ""
        if resume_b64 and resume_fn:
            UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
            dest = UPLOADS_DIR / resume_fn
            _write_file_base64(dest, resume_b64)
            profile["resume_path"] = f"data/uploads/{resume_fn}"
            profile["resume_filename"] = resume_fn
        save_profile(profile)

    if pack.get("preferences"):
        save_preferences(pack["preferences"])

    if pack.get("references"):
        save_references(pack["references"])

    if pack.get("scoring_state"):
        save_state(pack["scoring_state"])

    if pack.get("scoring_calibration"):
        save_calibration(pack["scoring_calibration"])
        try:
            write_calibration_md(pack["scoring_calibration"])
        except Exception:
            pass

    idx = _load_index()
    idx["active"] = safe
    _save_index(idx)

    try:
        from .scoring_state import ui_snapshot
        return ui_snapshot()
    except Exception:
        return {"ok": True, "name": safe}


def import_pack_from_path(src_path: Union[str, Path]) -> Dict[str, Any]:
    """Import a pack JSON file (with resume_base64 for portability)."""
    src = Path(src_path).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Pack file not found: {src}")

    raw = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Invalid pack JSON")

    name = _sanitize_name(raw.get("name") or src.stem)
    _ensure_dir()

    raw["name"] = name
    save_json(_pack_path(name), raw)

    idx = _load_index()
    names = list(idx.get("names") or [])
    if name not in names:
        names.append(name)
    idx["names"] = names
    _save_index(idx)

    return {"ok": True, "name": name, "imported_from": str(src)}


def export_pack_to_path(name: str, dest_path: Union[str, Path]) -> Dict[str, Any]:
    """Copy a pack JSON to an external path for sharing."""
    safe = _sanitize_name(name)
    pack_file = _pack_path(safe)
    if not pack_file.is_file():
        raise FileNotFoundError(f"Pack not found: {safe}")

    dest = Path(dest_path).expanduser().resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pack_file, dest)

    return {"ok": True, "name": safe, "exported_to": str(dest)}
