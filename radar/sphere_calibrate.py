# -*- coding: utf-8 -*-
"""One-time Cursor-based calibration for unknown activity spheres.

When the user declares an activity sphere that VacancyRadar doesn't recognise
(e.g. "курьер", "повар", "медсестра"), this module calls Cursor ONCE to generate
reject/pass keyword patterns for that sphere and caches them in calibration.json.

On subsequent runs the cached patterns are used at no cost.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Callable, List, Optional, Tuple

from .config import ROOT, load_config
from .cover_letter import _api_key
from .scoring_calibration import load_calibration, save_calibration

logger = logging.getLogger("vacancyradar.sphere_calibrate")

BRIDGE = ROOT / "cursor_bridge" / "analyze_profile.mjs"

_PATTERNS_KEY = "sphere_patterns"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_cached(sphere: str) -> Optional[dict]:
    """Return cached patterns dict for sphere, or None."""
    cal = load_calibration()
    return (cal.get(_PATTERNS_KEY) or {}).get(sphere.lower().strip())


def _save_cached(sphere: str, reject: List[str], pass_p: List[str]) -> None:
    """Persist calibrated patterns into calibration.json."""
    cal = load_calibration()
    bucket = cal.setdefault(_PATTERNS_KEY, {})
    bucket[sphere.lower().strip()] = {
        "reject": reject,
        "pass": pass_p,
        "calibrated_at": _now_iso(),
    }
    save_calibration(cal)


def calibrate_sphere_if_needed(
    sphere: str,
    cfg: Optional[dict] = None,
    on_progress: Optional[Callable[[str], None]] = None,
) -> Tuple[List[str], List[str]]:
    """Return (reject_patterns, pass_patterns) for the given sphere.

    • If sphere maps to a known category → returns ([], []) — sphere_filter handles it.
    • If unknown but cached in calibration.json → returns cached patterns (free).
    • If unknown and not cached → calls Cursor once, caches, returns patterns.

    The caller is responsible for applying the returned patterns to title matching.
    """
    from .sphere_filter import normalize_sphere_category

    def prog(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    sphere_s = (sphere or "").strip()
    if not sphere_s:
        return [], []

    if normalize_sphere_category(sphere_s):
        # Known sphere — sphere_filter already has patterns.
        return [], []

    cached = _load_cached(sphere_s)
    if cached:
        reject = [str(p) for p in (cached.get("reject") or []) if p]
        pass_p = [str(p) for p in (cached.get("pass") or []) if p]
        prog(
            f"Sphere calibration: кэш «{sphere_s}» — "
            f"{len(reject)} reject, {len(pass_p)} pass паттернов"
        )
        return reject, pass_p

    if not BRIDGE.exists():
        logger.warning("Sphere calibration: bridge not found: %s", BRIDGE)
        return [], []

    _cfg = cfg or load_config()
    api_key = _api_key(_cfg)
    if not api_key:
        logger.warning(
            "Sphere calibration: нет API-ключа, пропускаем для «%s»", sphere_s
        )
        return [], []

    prog(
        f"Sphere calibration: неизвестная сфера «{sphere_s}» — "
        "однократный запрос к Cursor…"
    )

    payload: dict = {
        "mode": "sphere_calibration",
        "sphere": sphere_s,
        "apiKey": api_key,
        "model": _cfg.get("model") or "composer-2.5",
        "cwd": str(ROOT),
    }

    try:
        with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as tf:
            tf.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            tmp_path = tf.name

        env = os.environ.copy()
        env["CURSOR_API_KEY"] = api_key

        result = subprocess.run(
            ["node", str(BRIDGE), tmp_path],
            capture_output=True,
            timeout=120,
            env=env,
        )
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

        if result.returncode != 0:
            err = (result.stderr or b"").decode("utf-8", errors="replace")
            logger.warning(
                "Sphere calibration FAIL «%s»: %s", sphere_s, err[:300]
            )
            return [], []

        raw = (result.stdout or b"").decode("utf-8", errors="replace").strip()
        data = json.loads(raw)

        reject = [str(p) for p in (data.get("reject") or []) if p]
        pass_p = [str(p) for p in (data.get("pass") or []) if p]

        _save_cached(sphere_s, reject, pass_p)
        prog(
            f"Sphere calibration: сохранено «{sphere_s}» — "
            f"{len(reject)} reject, {len(pass_p)} pass"
        )
        return reject, pass_p

    except Exception:
        logger.exception(
            "Sphere calibration: ошибка для «%s»", sphere_s
        )
        return [], []
