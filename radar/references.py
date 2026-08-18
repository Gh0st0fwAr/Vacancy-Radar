# -*- coding: utf-8 -*-
"""Gold-reference vacancy URLs + Cursor calibration cache for FIT signals."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from .config import DATA, load_json, save_json
from .preferences import append_upload_log

REFERENCES_PATH = DATA / "references.json"

DEFAULT_REFERENCES: Dict[str, Any] = {
    "urls": [],
    "calibration": None,
    "updated_at": "",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_urls(urls: Optional[Sequence[Any]]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    if not urls:
        return out
    for raw in urls:
        u = str(raw or "").strip()
        if not u:
            continue
        key = u.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(u)
    return out


def _coerce_references(raw: Any) -> Dict[str, Any]:
    data = dict(DEFAULT_REFERENCES)
    if not isinstance(raw, dict):
        return data
    data["urls"] = _normalize_urls(raw.get("urls") or [])
    cal = raw.get("calibration")
    data["calibration"] = cal if isinstance(cal, dict) else None
    data["updated_at"] = str(raw.get("updated_at") or "")
    return data


def load_references() -> Dict[str, Any]:
    return _coerce_references(load_json(REFERENCES_PATH, dict(DEFAULT_REFERENCES)))


def save_references(data: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = _coerce_references(data)
    if not cleaned.get("updated_at"):
        cleaned["updated_at"] = _now_iso()
    save_json(REFERENCES_PATH, cleaned)
    return cleaned


def set_urls(urls: Sequence[Any]) -> Dict[str, Any]:
    data = load_references()
    data["urls"] = _normalize_urls(urls)
    data["updated_at"] = _now_iso()
    saved = save_references(data)
    append_upload_log("references_urls", f"set {len(saved['urls'])} url(s)")
    return saved


def clear_calibration() -> Dict[str, Any]:
    data = load_references()
    data["calibration"] = None
    data["updated_at"] = _now_iso()
    saved = save_references(data)
    append_upload_log("references_calibration", "cleared")
    return saved


def set_calibration(calibration_dict: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    data = load_references()
    if calibration_dict is None:
        data["calibration"] = None
    elif isinstance(calibration_dict, dict):
        data["calibration"] = dict(calibration_dict)
    else:
        raise TypeError("calibration_dict must be a dict or None")
    data["updated_at"] = _now_iso()
    saved = save_references(data)
    append_upload_log(
        "references_calibration",
        "set" if saved.get("calibration") else "cleared",
    )
    return saved


def build_references_prompt_block(refs: Optional[Dict[str, Any]] = None) -> str:
    """Inject calibration as strong FIT gold examples (never override keyword rules)."""
    data = refs if refs is not None else load_references()
    cal = data.get("calibration")
    if not isinstance(cal, dict) or not cal:
        return ""

    summary = str(cal.get("summary") or "").strip()
    analyzed_at = str(cal.get("analyzed_at") or "").strip()
    items = cal.get("items") or []
    if not isinstance(items, list):
        items = []

    lines: List[str] = [
        "## Vacancy reference calibration (gold FIT examples)",
        "These are strong positive FIT signals from user-uploaded reference vacancies.",
        "USE them to ADD positive signals when the current vacancy resembles them.",
        "NEVER let these examples override Reject / Desirable / Neutral / Undesirable "
        "keyword preference rules — keyword Reject still means must reject; "
        "Desirable/Undesirable keyword rules still apply.",
    ]
    if analyzed_at:
        lines.append(f"Analyzed at: {analyzed_at}")
    if summary:
        lines.append(f"Summary: {summary}")

    for i, item in enumerate(items, 1):
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        score = item.get("score")
        reasons = item.get("reasons")
        excerpt = str(item.get("excerpt") or "").strip()
        lines.append(f"### Example {i}")
        if url:
            lines.append(f"- URL: {url}")
        if score is not None:
            lines.append(f"- Score: {score}")
        if reasons:
            if isinstance(reasons, (list, tuple)):
                lines.append("- Reasons: " + "; ".join(str(r) for r in reasons))
            else:
                lines.append(f"- Reasons: {reasons}")
        if excerpt:
            lines.append(f"- Excerpt: {excerpt[:1200]}")

    return "\n".join(lines).strip()


def invalidate_and_prepare_reupload(urls: Sequence[Any]) -> Dict[str, Any]:
    """Replace URLs, clear calibration, return state ready for re-analysis."""
    data = load_references()
    data["urls"] = _normalize_urls(urls)
    data["calibration"] = None
    data["updated_at"] = _now_iso()
    saved = save_references(data)
    append_upload_log(
        "references_reupload",
        f"prepared re-analysis for {len(saved['urls'])} url(s)",
    )
    return saved


def analyze_references_via_cursor(cfg: Optional[dict] = None) -> Dict[str, Any]:
    """Run reference calibration via search/upload layer hook (not implemented here).

    Lazily imports ``run_reference_calibration(urls, cfg)`` from
    ``radar.reference_calibrate`` when that module exists. Does not fetch vacancy
    pages itself.
    """
    data = load_references()
    urls = list(data.get("urls") or [])
    if not urls:
        raise ValueError("No reference URLs to analyze")

    try:
        from .reference_calibrate import run_reference_calibration  # type: ignore
    except ImportError as exc:
        raise NotImplementedError(
            "radar.reference_calibrate.run_reference_calibration is not available yet; "
            "search/upload layer should provide it."
        ) from exc

    calibration = run_reference_calibration(urls, cfg or {})
    if not isinstance(calibration, dict):
        raise TypeError("run_reference_calibration must return a dict")
    return set_calibration(calibration)
