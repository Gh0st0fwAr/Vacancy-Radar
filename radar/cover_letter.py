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
    except Exception:
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
    years = str(cfg.get("experience_years_label") or "").strip()
    pitch = (cfg.get("candidate_pitch") or "").strip()
    fmt = (cfg.get("work_format_phrase") or "Ищу удалённую работу").strip()
    target = int(cfg.get("salary_target") or 100000)
    closing = (cfg.get("cover_letter_closing") or "").strip()
    header = _header(cfg)

    parts = []
    if header:
        parts.extend([header, ""])
    parts.extend(
        [
            "Здравствуйте!",
            "",
            "Заинтересовала ваша вакансия " + title + ".",
            "",
        ]
    )
    if fmt:
        parts.append(fmt)
    if pitch:
        parts.extend(["", pitch, ""])
    elif years:
        role = (cfg.get("candidate_role") or "Специалист").strip()
        parts.extend(
            [
                "",
                "Я — " + role + ", опыт " + years + ".",
                "",
            ]
        )
    salary_line = (
        "Ориентир по компенсации — около "
        + f"{target:,}".replace(",", " ")
        + " ₽ на руки."
    )
    if salary:
        salary_line += " В карточке указано: " + salary + "."
    parts.append(salary_line)
    if closing:
        parts.extend(["", closing])
    else:
        parts.extend(["", "Готов ответить на вопросы по опыту и созвониться."])
    return _sanitize("\n".join(parts))
