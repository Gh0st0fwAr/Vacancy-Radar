# -*- coding: utf-8 -*-
"""Rule-based vacancy scoring. Missing salary is neutral."""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

from .refusal import text_looks_like_refusal


def _text(*parts: str) -> str:
    return " ".join(p or "" for p in parts).lower()


def score_vacancy(
    title: str,
    snippet: str = "",
    salary_text: str = "",
    schedule: str = "",
    experience: str = "",
    salary_floor: int = 120000,
    gate_threshold: int = 65,
) -> Tuple[int, List[str], bool]:
    """
    Returns (score 0-100, reasons, accept_candidate).
    Non-remote without remote option -> reject (score 0).
    gate_threshold: min score after a gated bonus (same as queue score_threshold).
    """
    gate = int(gate_threshold or 65)
    blob = _text(title, snippet, schedule, experience, salary_text)
    reasons: List[str] = []
    score = 0

    # Already refused by employer on HH — never queue.
    if text_looks_like_refusal(title, snippet):
        return 0, ["HH employer refusal"], False

    # Hard filters
    remote_ok = any(
        x in blob
        for x in (
            "удал",
            "remote",
            "дистанц",
            "можно удалённо",
            "можно удаленно",
            "формат работы: удал",
        )
    )
    office_only = any(x in blob for x in ("только офис", "офисная", "в офисе")) and not remote_ok
    if office_only or (schedule and "удал" not in schedule.lower() and "remote" not in schedule.lower() and not remote_ok):
        # if schedule explicitly remote from HH filter, trust it
        if "удал" in (schedule or "").lower() or "remote" in (schedule or "").lower():
            remote_ok = True
        else:
            return 0, ["Не удалёнка"], False

    if not remote_ok and "удал" not in (schedule or "").lower():
        # HH search already filtered remote — allow if schedule empty
        if schedule:
            return 0, ["Формат не remote"], False

    score += 20
    reasons.append("+20 remote")

    # Stack
    has_vue3 = bool(re.search(r"vue\s*3|vue3", blob))
    has_vue2 = bool(re.search(r"vue\s*2|vue2", blob))
    has_vue = bool(re.search(r"(?<![a-z])vue(?![a-z0-9])", blob)) and not bool(
        re.search(r"\b(no|without|без)\s+vue\b", blob)
    )
    if has_vue3 or has_vue2:
        has_vue = True
    has_nuxt = "nuxt" in blob
    has_ts = "typescript" in blob or re.search(r"\bts\b", blob) is not None
    has_pinia = "pinia" in blob
    has_fullstack = any(
        x in blob
        for x in (
            "fullstack",
            "full-stack",
            "full stack",
            "фуллстек",
            "фулстек",
            "full‑stack",
        )
    )
    has_node = bool(
        re.search(r"\bnode\.?js\b|\bnodejs\b|nestjs|\bexpress\b", blob)
    ) or ("node" in blob and has_fullstack)
    react_heavy = ("react" in blob or "next.js" in blob or "nextjs" in blob) and not has_vue and not has_nuxt
    angular_heavy = "angular" in blob and not has_vue

    if react_heavy or angular_heavy:
        return 5, ["Стек не Vue/Nuxt"], False

    nuxt_only = False
    if has_vue3:
        score += 25
        reasons.append("+25 Vue 3")
    elif has_vue2:
        score += 25
        reasons.append("+25 Vue 2")
    elif has_vue:
        score += 25
        reasons.append("+25 Vue")
    elif has_nuxt:
        nuxt_only = True
    elif has_fullstack and has_node:
        score += 14
        reasons.append("+14 Fullstack + Node (пробуем)")
    elif has_fullstack and has_ts:
        score += 15
        reasons.append("+15 Fullstack + TypeScript (пробуем)")
    elif has_fullstack:
        score += 10
        reasons.append("+10 Fullstack (без явного Vue — на оценку)")
    else:
        return 10, ["Нет Vue/Nuxt/Fullstack в тексте"], False

    if has_ts:
        score += 20
        reasons.append("+20 TypeScript")
    else:
        score += 5
        reasons.append("+5 без явного TS")

    if has_pinia:
        score += 10
        reasons.append("+10 Pinia")

    # Salary numbers / noise before threshold-gated bonuses
    sal = parse_salary_max(salary_text)
    negotiable = sal is None or is_salary_negotiable(salary_text)
    salary_missing = bool(negotiable and sal is None)
    if sal is not None:
        if sal >= salary_floor:
            score += 8
            reasons.append(f"+8 ЗП≥{salary_floor}")
        else:
            score -= 12
            reasons.append(f"-12 ЗП низкая (~{sal})")
    if negotiable and sal is not None and "договор" in (salary_text or "").lower():
        reasons.append("ЗП обсуждаема")

    if any(x in blob for x in ("1с", "bitrix", "битрикс", "wordpress", "php-разработ")):
        score -= 20
        reasons.append("-20 чужой стек в описании")

    # Threshold-gated bonuses (apply only if score+bonus >= gate)
    if nuxt_only:
        if score + 20 >= gate:
            score += 20
            reasons.append(f"+20 Nuxt без Vue (дотягивает до {gate}+)")
        else:
            reasons.append(f"Nuxt без Vue (без +20: даже с бонусом < {gate})")

    if has_nuxt and has_vue:
        if score + 25 >= gate:
            score += 25
            reasons.append(f"+25 Nuxt + Vue (дотягивает до {gate}+)")
        else:
            reasons.append(f"Nuxt + Vue (без +25: даже с бонусом < {gate})")

    if has_fullstack and (has_vue or has_nuxt):
        if score + 20 >= gate:
            score += 20
            reasons.append(f"+20 Fullstack рядом с Vue/Nuxt (дотягивает до {gate}+)")
        else:
            reasons.append(f"Fullstack рядом с Vue/Nuxt (без +20: даже с бонусом < {gate})")

    has_middle_plus = any(
        x in blob for x in ("middle+", "mid+", "мидл+", "middle +", "мидл +")
    )
    has_middle = (not has_middle_plus) and any(
        x in blob for x in ("middle", "мидл")
    )
    if has_middle_plus:
        if score + 15 >= gate:
            score += 15
            reasons.append(f"+15 Middle+ (дотягивает до {gate}+)")
        else:
            reasons.append(f"Middle+ (без +15: даже с бонусом < {gate})")
    elif has_middle:
        if score + 17 >= gate:
            score += 17
            reasons.append(f"+17 Middle (дотягивает до {gate}+)")
        else:
            reasons.append(f"Middle (без +17: даже с бонусом < {gate})")
    elif "senior" in blob or "сеньор" in blob:
        score += 4
        reasons.append("+4 Senior (можно пробовать)")
    elif "junior" in blob or "джун" in blob:
        reasons.append("Junior/опыт <3 — без штрафа (рассматриваем)")

    if salary_missing:
        if score + 20 >= gate:
            score += 20
            reasons.append(f"+20 ЗП не указана (дотягивает до {gate}+)")
        else:
            reasons.append(f"ЗП не указана / обсуждаемо (без +20: даже с бонусом < {gate})")

    score = max(0, min(100, score))
    return score, reasons, True


def is_salary_negotiable(text: str) -> bool:
    if not text or not str(text).strip():
        return True
    t = str(text).lower()
    return any(
        x in t
        for x in (
            "договор",
            "обсужд",
            "по собеседован",
            "на собеседован",
            "по результатам",
            "не указан",
        )
    )


def parse_salary_max(text: str) -> int | None:
    if not text:
        return None
    if is_salary_negotiable(text) and not re.search(r"\d{5,}", text.replace(" ", "").replace("\xa0", "")):
        return None
    t = text.replace("\xa0", " ").replace(" ", "")
    nums = [int(x) for x in re.findall(r"\d{5,7}", t)]
    if not nums:
        nums = [int(x) for x in re.findall(r"\d{3,7}", text.replace("\xa0", "").replace(" ", ""))]
        nums = [n for n in nums if n >= 40000]
    if not nums:
        return None
    return max(nums)


def explain(score: int, reasons: List[str]) -> str:
    return f"{score}%\n" + "\n".join(reasons)
