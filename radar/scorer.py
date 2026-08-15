# -*- coding: utf-8 -*-
"""Rule-based vacancy scoring. Missing salary is neutral."""
from __future__ import annotations

import re
from typing import Dict, List, Tuple


def _text(*parts: str) -> str:
    return " ".join(p or "" for p in parts).lower()


def score_vacancy(
    title: str,
    snippet: str = "",
    salary_text: str = "",
    schedule: str = "",
    experience: str = "",
    salary_floor: int = 120000,
) -> Tuple[int, List[str], bool]:
    """
    Returns (score 0-100, reasons, accept_candidate).
    Non-remote without remote option -> reject (score 0).
    """
    blob = _text(title, snippet, schedule, experience, salary_text)
    reasons: List[str] = []
    score = 0

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
    has_vue = "vue" in blob
    has_nuxt = "nuxt" in blob
    has_ts = "typescript" in blob or re.search(r"\bts\b", blob) is not None
    has_pinia = "pinia" in blob
    react_heavy = ("react" in blob or "next.js" in blob or "nextjs" in blob) and not has_vue and not has_nuxt
    angular_heavy = "angular" in blob and not has_vue

    if react_heavy or angular_heavy:
        return 5, ["Стек не Vue/Nuxt"], False

    if has_vue3:
        score += 25
        reasons.append("+25 Vue 3")
    elif has_vue:
        score += 18
        reasons.append("+18 Vue")
    elif has_nuxt:
        score += 15
        reasons.append("+15 Nuxt (без явного Vue)")
    else:
        return 10, ["Нет Vue/Nuxt в тексте"], False

    if has_nuxt and has_vue:
        score += 12
        reasons.append("+12 Nuxt")
    elif has_nuxt:
        score += 8
        reasons.append("+8 Nuxt")

    if has_ts:
        score += 20
        reasons.append("+20 TypeScript")
    else:
        score += 5
        reasons.append("+5 без явного TS")

    if has_pinia:
        score += 5
        reasons.append("+5 Pinia")

    # Level — любой опыт ок; junior не режем жёстко
    if any(x in blob for x in ("middle", "мидл", "mid+", "middle+")):
        score += 10
        reasons.append("+10 Middle")
    elif "senior" in blob or "сеньор" in blob:
        score += 4
        reasons.append("+4 Senior (можно пробовать)")
    elif "junior" in blob or "джун" in blob:
        reasons.append("Junior/опыт <3 — без штрафа (рассматриваем)")

    # Salary: missing / «по договорённости» = neutral
    sal = parse_salary_max(salary_text)
    negotiable = sal is None or is_salary_negotiable(salary_text)
    if negotiable and sal is None:
        reasons.append("ЗП не указана / обсуждаемо (нейтрально)")
    elif sal is not None:
        if sal >= salary_floor:
            score += 8
            reasons.append(f"+8 ЗП≥{salary_floor}")
        else:
            # низкая вилка — минус, но вакансию не отбрасываем на уровне фильтра опыта
            score -= 12
            reasons.append(f"-12 ЗП низкая (~{sal})")
    if negotiable and sal is not None and "договор" in (salary_text or "").lower():
        reasons.append("ЗП обсуждаема")

    # Noise
    if any(x in blob for x in ("1с", "bitrix", "битрикс", "wordpress", "php-разработ")):
        score -= 20
        reasons.append("-20 чужой стек в описании")

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
