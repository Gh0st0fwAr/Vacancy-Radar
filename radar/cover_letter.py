# -*- coding: utf-8 -*-
"""Cover letters: local profile template (python-only)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time as _time
from typing import Dict, List, Optional, Sequence, Tuple

from .config import ROOT, load_config
from .candidate_profile import build_candidate_block, links_dict, load_scoring_context
from .metrics_log import append_event

BRIDGE = ROOT / "cursor_bridge" / "generate_letter.mjs"
RULES_CWD = ROOT.parent

STALE_MARKERS = (
    "Middle frontend",
    "enterprise NMS",
    "gh0st0fwar.github.io",
    "@daniil_virin",
)


def _header(cfg: dict) -> str:
    lines = []
    port = (cfg.get("portfolio_url") or "").strip()
    if port:
        lines.append("\u041f\u043e\u0440\u0442\u0444\u043e\u043b\u0438\u043e: " + port)
    tg = (cfg.get("telegram") or "").strip()
    if tg:
        if not tg.startswith("@"):
            tg = "@" + tg
        lines.append("Telegram: " + tg)
    email = (cfg.get("email") or "").strip()
    if email:
        lines.append("Email: " + email)
    return "\n".join(lines)


def make_cover_letter(
    vacancy_title: str,
    *,
    company: str = "",
    description: str = "",
    salary: str = "",
    reasons: Optional[Sequence[str]] = None,
    force_local: bool = False,
) -> Tuple[str, str]:
    title = (vacancy_title or "\u0412\u0430\u043a\u0430\u043d\u0441\u0438\u044f").strip()
    company = (company or "").strip()
    description = (description or "").strip()
    salary = (salary or "").strip()
    reasons_list = list(reasons or [])

    cfg = load_config()
    if bool(cfg.get("python_only", False)):
        force_local = True
    use_cursor = bool(cfg.get("cover_letter_via_cursor", False)) and not force_local
    t0 = _time.perf_counter()
    if use_cursor:
        letter, meta = _via_cursor(
            title=title,
            company=company,
            description=description,
            salary=salary,
            reasons=reasons_list,
            cfg=cfg,
        )
        if letter:
            elapsed = int(meta.get("elapsed_ms") or (_time.perf_counter() - t0) * 1000)
            append_event(
                "letter",
                title=title[:120],
                company=company[:80],
                source="cursor",
                elapsed_ms=elapsed,
                usage=meta.get("usage"),
                letter_chars=len(letter),
            )
            return letter, "cursor"

    letter = _via_local(
        title=title,
        company=company,
        description=description,
        salary=salary,
        reasons=reasons_list,
        cfg=cfg,
    )
    elapsed = int((_time.perf_counter() - t0) * 1000)
    append_event(
        "letter",
        title=title[:120],
        company=company[:80],
        source="local",
        elapsed_ms=elapsed,
        usage=None,
        letter_chars=len(letter or ""),
    )
    return letter, "local"


def is_stale_template(letter: str) -> bool:
    text = letter or ""
    return any(m in text for m in STALE_MARKERS)


def _api_key(cfg: dict) -> str:
    return (
        (cfg.get("cursor_api_key") or "").strip()
        or os.environ.get("CURSOR_API_KEY", "").strip()
        or os.environ.get("CURSOR_API_KEY_ALT", "").strip()
    )


def _via_cursor(
    *,
    title: str,
    company: str,
    description: str,
    salary: str,
    reasons: List[str],
    cfg: dict,
) -> Tuple[Optional[str], dict]:
    meta: dict = {}
    if not BRIDGE.exists():
        return None, meta
    key = _api_key(cfg)
    if not key:
        return None, meta

    links = links_dict()
    payload = {
        "title": title,
        "company": company,
        "description": description,
        "salary": salary,
        "reasons": reasons,
        "apiKey": key,
        "model": cfg.get("cursor_model") or "composer-2.5",
        "cwd": str(RULES_CWD),
        "returnMeta": True,
        "candidateProfile": build_candidate_block(),
        "scoringRules": load_scoring_context(),
        "portfolioUrl": links["portfolioUrl"],
        "githubUrl": links["githubUrl"],
        "resumePath": links.get("resumePath") or "",
    }
    timeout = int(cfg.get("cover_letter_timeout_sec") or 90)
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
        if proc.returncode != 0:
            return None, meta
        raw = (proc.stdout or "").strip()
        letter = ""
        if raw.startswith("{"):
            data = json.loads(raw)
            letter = str(data.get("letter") or "").strip()
            meta["usage"] = data.get("usage")
            meta["elapsed_ms"] = data.get("elapsed_ms")
        else:
            letter = raw
        if len(letter) < 120:
            return None, meta
        return _sanitize(letter), meta
    except Exception as e:
        meta["error"] = str(e)[:240]
        try:
            append_event("letter", title=title[:120], source="cursor_failed", error=meta["error"])
        except Exception:
            pass
        return None, meta


def _sanitize(letter: str) -> str:
    text = letter.strip()
    text = re.sub(r"^```[\w]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    lines = []
    for line in text.splitlines():
        low = line.lower().strip()
        if low.startswith("\u0441\u0441\u044b\u043b\u043a\u0430 \u043d\u0430 \u0432\u0430\u043a\u0430\u043d\u0441\u0438\u044e"):
            continue
        if re.match(r"^https?://.*(hh\.ru|getmatch|habr|remote-job)", low):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _via_local(
    *,
    title: str,
    company: str,
    description: str,
    salary: str,
    reasons: Sequence[str],
    cfg: dict,
) -> str:
    role = (cfg.get("candidate_role") or "\u0421\u043f\u0435\u0446\u0438\u0430\u043b\u0438\u0441\u0442").strip()
    years = str(cfg.get("experience_years_label") or "1").strip()
    pitch = (cfg.get("candidate_pitch") or "").strip()
    fmt = (cfg.get("work_format_phrase") or "\u0418\u0449\u0443 \u0443\u0434\u0430\u043b\u0451\u043d\u043d\u0443\u044e \u0440\u0430\u0431\u043e\u0442\u0443").strip()
    target = int(cfg.get("salary_target") or 100000)
    company_bit = (" \u0432 " + company) if company else ""
    header = _header(cfg)

    parts = []
    if header:
        parts.extend([header, ""])
    parts.extend(
        [
            "\u0417\u0434\u0440\u0430\u0432\u0441\u0442\u0432\u0443\u0439\u0442\u0435!",
            "\u0417\u0430\u0438\u043d\u0442\u0435\u0440\u0435\u0441\u043e\u0432\u0430\u043b\u0430 \u0432\u0430\u0448\u0430 \u0432\u0430\u043a\u0430\u043d\u0441\u0438\u044f " + title + ".",
            "",
            "\u042f \u2014 " + role + ", \u043e\u043f\u044b\u0442 ~" + years + " \u0433. "
            "\u0412\u0430\u043a\u0430\u043d\u0441\u0438\u044f \u00ab" + title + "\u00bb" + company_bit + " "
            "\u043f\u043e \u043f\u0440\u043e\u0444\u0438\u043b\u044e \u0431\u043b\u0438\u0437\u043a\u0430 \u043a \u043c\u043e\u0435\u043c\u0443 \u043e\u043f\u044b\u0442\u0443.",
            "",
        ]
    )
    if pitch:
        parts.extend([pitch, ""])
    salary_note = ""
    if salary:
        salary_note = " \u0412 \u043a\u0430\u0440\u0442\u043e\u0447\u043a\u0435 \u0443\u043a\u0430\u0437\u0430\u043d\u043e: " + salary + "."
    parts.append(
        fmt + ". \u041e\u0440\u0438\u0435\u043d\u0442\u0438\u0440 \u043f\u043e \u043a\u043e\u043c\u043f\u0435\u043d\u0441\u0430\u0446\u0438\u0438 ~"
        + str(target // 1000)
        + "k \u043d\u0430 \u0440\u0443\u043a\u0438."
        + salary_note
    )
    parts.extend(
        [
            "",
            "\u0413\u043e\u0442\u043e\u0432 \u043e\u0442\u0432\u0435\u0442\u0438\u0442\u044c \u043d\u0430 \u0432\u043e\u043f\u0440\u043e\u0441\u044b \u043f\u043e \u043e\u043f\u044b\u0442\u0443 \u0438 \u0441\u043e\u0437\u0432\u043e\u043d\u0438\u0442\u044c\u0441\u044f.",
        ]
    )
    return _sanitize("\n".join(parts))
