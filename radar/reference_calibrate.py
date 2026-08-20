# -*- coding: utf-8 -*-
"""Calibrate Cursor scoring from user-uploaded reference vacancy URLs.

Fetches vacancy text (via Chrome CDP when possible, else urllib), asks Cursor SDK
for a short FIT summary per URL, stores calibration in data/references.json.
Re-upload clears previous calibration first (see references.invalidate_and_prepare_reupload).
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from .candidate_profile import build_candidate_block, load_scoring_context
from .config import ROOT, load_config
from .cover_letter import _api_key
from .preferences import append_upload_log, build_preferences_prompt_block
from .references import set_calibration

BRIDGE = ROOT / "cursor_bridge" / "score_vacancy.mjs"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fetch_url_text(url: str, timeout: float = 25.0) -> str:
    """Best-effort plain fetch (HH and many boards need browser; CDP used when available)."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1251", errors="replace")
    # Strip tags lightly
    import re

    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:12000]


def _fetch_via_cdp(url: str, settle: float = 1.2) -> Optional[str]:
    try:
        from .cdp import open_session
        from .chrome_lock import chrome_exclusive

        js = r"""
        (() => {
          const needLogin = /account\/login/i.test(location.href);
          const titleEl = document.querySelector('h1') || document.querySelector('[data-qa="vacancy-title"]');
          const body = (document.body && document.body.innerText) || '';
          return {
            needLogin,
            title: titleEl ? (titleEl.innerText||'').trim() : '',
            text: body.slice(0, 12000),
          };
        })()
        """
        with chrome_exclusive(timeout=90):
            session = open_session(url)
            try:
                session.navigate(url, settle=settle)
                data = session.evaluate(js, timeout=20)
            finally:
                session.close()
        if not isinstance(data, dict) or data.get("needLogin"):
            return None
        title = str(data.get("title") or "").strip()
        text = str(data.get("text") or "").strip()
        if not text:
            return None
        return (f"{title}\n\n{text}").strip()[:12000]
    except Exception:
        return None


def fetch_reference_text(url: str, cfg: Optional[dict] = None) -> str:
    cfg = cfg or {}
    settle = float(cfg.get("vacancy_settle_sec") or 1.1)
    text = _fetch_via_cdp(url, settle=settle)
    if text:
        return text
    try:
        return _fetch_url_text(url)
    except Exception as exc:
        return f"(failed to fetch: {exc})"


def _score_reference_via_cursor(
    *,
    url: str,
    text: str,
    cfg: dict,
) -> Dict[str, Any]:
    key = _api_key(cfg)
    if not key or not BRIDGE.exists():
        return {
            "url": url,
            "score": 0,
            "accept": False,
            "reasons": ["cursor-unavailable"],
            "excerpt": (text or "")[:500],
        }
    title = (text or "").split("\n", 1)[0][:160] or "Reference vacancy"
    payload = {
        "title": title,
        "company": "",
        "description": text,
        "salary": "",
        "schedule": "",
        "experience": "",
        "threshold": int(cfg.get("score_threshold") or 70),
        "apiKey": key,
        "model": cfg.get("cursor_model") or "composer-2.5",
        "cwd": str(ROOT.parent),
        "candidateProfile": build_candidate_block(),
        "scoringRules": (
            load_scoring_context()
            + "\n\n"
            + "This vacancy is a USER REFERENCE (gold FIT example). "
            "Score honestly how well it matches the candidate; extract transferable signals."
        ),
        "portfolioUrl": "",
        "githubUrl": "",
        "resumePath": "",
    }
    # Prefer live profile links if present
    try:
        from .user_profile import links_dict

        links = links_dict()
        payload["portfolioUrl"] = links.get("portfolioUrl") or ""
        payload["githubUrl"] = links.get("githubUrl") or ""
        payload["resumePath"] = links.get("resumePath") or ""
    except Exception:
        pass

    timeout = int(cfg.get("cursor_score_timeout_sec") or 120)
    try:
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
        raw = (proc.stdout or "").strip()
        data = json.loads(raw) if raw.startswith("{") else {}
        if not isinstance(data, dict):
            data = {}
        return {
            "url": url,
            "score": int(data.get("score") or 0),
            "accept": bool(data.get("accept")),
            "reasons": list(data.get("reasons") or [])[:8],
            "excerpt": (text or "")[:800],
        }
    except Exception as exc:
        return {
            "url": url,
            "score": 0,
            "accept": False,
            "reasons": [f"calib-error:{str(exc)[:120]}"],
            "excerpt": (text or "")[:500],
        }


def run_reference_calibration(
    urls: Sequence[str],
    cfg: Optional[dict] = None,
) -> Dict[str, Any]:
    """Analyze reference URLs and return calibration dict for references.set_calibration."""
    cfg = cfg or load_config()
    items: List[Dict[str, Any]] = []
    t0 = time.time()
    for url in urls:
        u = str(url or "").strip()
        if not u:
            continue
        append_upload_log("reference_fetch", f"fetch {u}")
        text = fetch_reference_text(u, cfg=cfg)
        append_upload_log("reference_score", f"score {u}")
        items.append(_score_reference_via_cursor(url=u, text=text, cfg=cfg))

    strong = [it for it in items if int(it.get("score") or 0) >= int(cfg.get("score_threshold") or 70)]
    summary_bits = [
        f"Analyzed {len(items)} reference URL(s); {len(strong)} at/above threshold.",
        "Treat high-scoring references as gold FIT examples: boost similar stack/role signals.",
        "Never override Reject / Desirable / Neutral / Undesirable keyword rules.",
    ]
    if strong:
        reasons = []
        for it in strong:
            for r in it.get("reasons") or []:
                reasons.append(str(r))
        if reasons:
            summary_bits.append("Signals: " + "; ".join(reasons[:12]))

    calibration = {
        "summary": " ".join(summary_bits),
        "analyzed_at": _now_iso(),
        "elapsed_sec": round(time.time() - t0, 1),
        "items": items,
        "preferences_snapshot": build_preferences_prompt_block(),
    }
    return calibration


def upload_references_and_calibrate(
    urls: Sequence[str],
    cfg: Optional[dict] = None,
) -> Dict[str, Any]:
    """Replace URLs, clear old calibration, run Cursor analysis, save new calibration."""
    from .references import analyze_references_via_cursor, invalidate_and_prepare_reupload

    invalidate_and_prepare_reupload(urls)
    # analyze_references_via_cursor imports run_reference_calibration from this module
    return analyze_references_via_cursor(cfg)
