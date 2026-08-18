# -*- coding: utf-8 -*-
"""User-uploaded candidate profile for Cursor scoring / letters.

Storage: data/user_profile.json
Uploads: data/uploads/ (resume file + resume_text.txt cache)
"""
from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .config import DATA, ROOT, load_json, save_json

logger = logging.getLogger("vacancyradar.user_profile")

PROFILE_PATH = DATA / "user_profile.json"
UPLOADS_DIR = DATA / "uploads"
RESUME_TEXT_CACHE = UPLOADS_DIR / "resume_text.txt"
UPLOAD_LOG_PATH = DATA / "upload_log.jsonl"

EMPTY_PROFILE: Dict[str, str] = {
    "resume_path": "",
    "resume_filename": "",
    "portfolio_url": "",
    "github_url": "",
    "telegram": "",
    "email": "",
    "updated_at": "",
}

PathLike = Union[str, Path]

_TEXT_SUFFIXES = {".txt", ".md", ".markdown", ".text"}
_PDF_SUFFIXES = {".pdf"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_uploads() -> Path:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    return UPLOADS_DIR


def _normalize_profile(raw: Any) -> Dict[str, str]:
    out = dict(EMPTY_PROFILE)
    if isinstance(raw, dict):
        for key in EMPTY_PROFILE:
            val = raw.get(key, "")
            out[key] = "" if val is None else str(val)
    return out


def load_profile() -> Dict[str, str]:
    """Load profile from data/user_profile.json (empty schema if missing)."""
    return _normalize_profile(load_json(PROFILE_PATH, dict(EMPTY_PROFILE)))


def save_profile(profile: Dict[str, Any]) -> Dict[str, str]:
    """Persist profile; returns normalized dict."""
    data = _normalize_profile(profile)
    data["updated_at"] = data.get("updated_at") or _utc_now()
    DATA.mkdir(parents=True, exist_ok=True)
    save_json(PROFILE_PATH, data)
    return data


def _safe_filename(name: str) -> str:
    base = Path(name or "").name.strip() or "resume"
    base = re.sub(r"[^\w.\-()+ ]+", "_", base, flags=re.UNICODE)
    base = base.strip(" ._") or "resume"
    if len(base) > 140:
        stem = Path(base).stem[:110]
        suf = Path(base).suffix[:20]
        base = f"{stem}{suf}" if suf else stem
    return base


def resolve_resume_path(profile: Optional[Dict[str, Any]] = None) -> Optional[Path]:
    """Resolve resume_path relative to VacancyRadar root, or absolute under uploads."""
    p = profile if profile is not None else load_profile()
    raw = (p.get("resume_path") or "").strip()
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    else:
        path = path.resolve()
    return path


def is_profile_ready() -> bool:
    """True when configured resume file exists and is readable."""
    path = resolve_resume_path()
    if path is None or not path.is_file():
        return False
    try:
        with path.open("rb") as f:
            f.read(1)
        return True
    except OSError:
        return False


def _append_upload_log(row: Dict[str, Any]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    try:
        with UPLOAD_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as exc:
        logger.warning("upload_log append failed: %s", exc)


def _extract_pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(parts).strip()


def _extract_resume_text(path: Path) -> str:
    suf = path.suffix.lower()
    if suf in _PDF_SUFFIXES:
        try:
            return _extract_pdf_text(path)
        except Exception as exc:
            logger.warning("PDF extract failed for %s: %s", path, exc)
            return ""
    if suf in _TEXT_SUFFIXES or suf == "":
        try:
            return path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError as exc:
            logger.warning("Text read failed for %s: %s", path, exc)
            return ""
    # Unknown binary-ish: try utf-8 read as last resort
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""


def _write_text_cache(text: str) -> None:
    _ensure_uploads()
    RESUME_TEXT_CACHE.write_text(text or "", encoding="utf-8")


def _truncate(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if max_chars > 0 and len(text) > max_chars:
        return text[: max_chars - 20] + "\n...[truncated]..."
    return text


def upload_resume(src_path: PathLike) -> Dict[str, str]:
    """
    Copy resume into data/uploads/ with a safe name, cache extracted text,
    update profile, append upload_log.jsonl.
    """
    src = Path(src_path).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Resume file not found: {src}")

    _ensure_uploads()
    safe = _safe_filename(src.name)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest_name = f"{stamp}_{safe}"
    dest = UPLOADS_DIR / dest_name
    shutil.copy2(src, dest)

    text = _extract_resume_text(dest)
    _write_text_cache(text)

    rel = f"data/uploads/{dest_name}".replace("\\", "/")
    profile = load_profile()
    profile["resume_path"] = rel
    profile["resume_filename"] = src.name
    profile["updated_at"] = _utc_now()
    saved = save_profile(profile)

    _append_upload_log(
        {
            "ts": _utc_now(),
            "event": "upload_resume",
            "src": str(src),
            "dest": rel,
            "filename": src.name,
            "bytes": dest.stat().st_size if dest.is_file() else 0,
            "text_chars": len(text),
        }
    )
    logger.info("Resume uploaded: %s -> %s (%s chars text)", src.name, rel, len(text))
    return saved


def set_links(
    portfolio_url: Optional[str] = None,
    github_url: Optional[str] = None,
    telegram: Optional[str] = None,
    email: Optional[str] = None,
) -> Dict[str, str]:
    """Update optional portfolio / GitHub / contact fields (None = leave unchanged)."""
    profile = load_profile()
    if portfolio_url is not None:
        profile["portfolio_url"] = str(portfolio_url).strip()
    if github_url is not None:
        profile["github_url"] = str(github_url).strip()
    if telegram is not None:
        profile["telegram"] = str(telegram).strip()
    if email is not None:
        profile["email"] = str(email).strip()
    profile["updated_at"] = _utc_now()
    return save_profile(profile)


def load_resume_text(max_chars: int = 14000) -> str:
    """Load resume text from cache, else extract from configured resume file."""
    if RESUME_TEXT_CACHE.is_file():
        try:
            cached = RESUME_TEXT_CACHE.read_text(encoding="utf-8", errors="replace")
            if cached.strip():
                return _truncate(cached, max_chars)
        except OSError:
            pass

    path = resolve_resume_path()
    if path is None or not path.is_file():
        return ""

    text = _extract_resume_text(path)
    if text:
        try:
            _write_text_cache(text)
        except OSError as exc:
            logger.warning("Could not write resume text cache: %s", exc)
    return _truncate(text, max_chars)


def clear_profile() -> Dict[str, str]:
    """Clear resume refs and links; keep empty schema. Remove text cache if present."""
    old = load_profile()
    old_path = resolve_resume_path(old)

    empty = dict(EMPTY_PROFILE)
    empty["updated_at"] = _utc_now()
    saved = save_profile(empty)

    try:
        if RESUME_TEXT_CACHE.is_file():
            RESUME_TEXT_CACHE.unlink()
    except OSError:
        pass

    # Best-effort: remove previous upload if it lived under data/uploads/
    try:
        if old_path is not None and old_path.is_file():
            uploads_root = UPLOADS_DIR.resolve()
            if uploads_root in old_path.resolve().parents or old_path.resolve().parent == uploads_root:
                old_path.unlink()
    except OSError:
        pass

    logger.info("User profile cleared")
    return saved


def links_dict() -> Dict[str, str]:
    """Links / contacts for Cursor SDK scoring / letter payload."""
    p = load_profile()
    path = resolve_resume_path(p)
    return {
        "portfolioUrl": (p.get("portfolio_url") or "").strip(),
        "githubUrl": (p.get("github_url") or "").strip(),
        "resumePath": str(path) if path else "",
        "telegram": (p.get("telegram") or "").strip(),
        "email": (p.get("email") or "").strip(),
    }


def build_candidate_block() -> str:
    """
    Candidate context block for Cursor prompts.
    If resume is missing, return a clear soft-fail message (do not invent a profile).
    """
    if not is_profile_ready():
        return (
            "=== CANDIDATE PROFILE EMPTY ===\n"
            "No readable resume is configured in data/user_profile.json "
            "(upload a resume via upload_resume first).\n"
            "Scoring MUST fail soft: return score=0, accept=false, "
            "reasons=[\"profile-empty\"]. Do NOT invent candidate skills or experience.\n"
            "=== END CANDIDATE ==="
        )

    profile = load_profile()
    resume = load_resume_text()
    path = resolve_resume_path(profile)
    portfolio = (profile.get("portfolio_url") or "").strip()
    github = (profile.get("github_url") or "").strip()
    filename = (profile.get("resume_filename") or (path.name if path else "")).strip()

    lines = [
        "=== CANDIDATE (trust this block; score vacancy FIT against it) ===",
        f"Resume source: {filename or 'uploaded resume'}",
    ]
    if path:
        lines.append(f"Resume file path: {path}")
    if portfolio:
        lines.append(f"Portfolio: {portfolio}")
    if github:
        lines.append(f"GitHub: {github}")

    lines.extend(
        [
            "",
            "IMPORTANT:",
            "- Full resume text is embedded below — treat it as read.",
            "- Portfolio / GitHub URLs (if present) ARE scoring context.",
            "- Do NOT fail scoring because URLs cannot be fetched online.",
            "- Judge FIT from this context + vacancy text. Do NOT apply Python rules-engine point formulas.",
            "",
            "FULL RESUME:",
            resume if resume.strip() else "(WARNING: resume file present but text extraction returned empty)",
            "=== END CANDIDATE ===",
        ]
    )
    return "\n".join(lines)
