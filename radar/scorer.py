# -*- coding: utf-8 -*-
"""Profile-only rule scoring (python-only branch). No Vue legacy."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .refusal import text_looks_like_refusal


def _text(*parts: str) -> str:
    return " ".join(p or "" for p in parts).lower().replace("\u0451", "\u0435")


def score_vacancy(
    title: str,
    snippet: str = "",
    salary_text: str = "",
    schedule: str = "",
    experience: str = "",
    salary_floor: int = 120000,
    salary_good: int = 140000,
    gate_threshold: int = 65,
) -> Tuple[int, List[str], bool]:
    """
    Returns (score 0-100, reasons, accept_candidate).
    Non-remote without remote option -> reject (score 0).
    gate_threshold: min score after a gated bonus (same as queue score_threshold).
    Salary: >=salary_good → +20; >=salary_floor → +17; missing → +20 only if score+20 >= 70.
    """
    gate = int(gate_threshold or 65)
    floor = int(salary_floor or 120000)
    good = int(salary_good or 140000)
    if good < floor:
        good = floor
    blob = _text(title, snippet, schedule, experience, salary_text)
    reasons: List[str] = []
    score = 0


def _as_list(val: Any) -> List[str]:
    if val is None:
        return []
    if isinstance(val, str):
        parts = re.split(r"[,;\n]+", val)
        return [p.strip() for p in parts if p.strip()]
    if isinstance(val, (list, tuple)):
        out: List[str] = []
        for x in val:
            out.extend(_as_list(x))
        return out
    s = str(val).strip()
    return [s] if s else []


_ALIASES: Dict[str, List[str]] = {
    "support": [
        "support",
        "\u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a",
        "\u0442\u0435\u0445\u043f\u043e\u0434\u0434\u0435\u0440\u0436",
        "helpdesk",
        "help desk",
        "service desk",
    ],
    "\u0442\u0435\u0445\u043d\u0438\u0447\u0435\u0441\u043a\u0430\u044f \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430": [
        "\u0442\u0435\u0445\u043d\u0438\u0447\u0435\u0441\u043a\u0430\u044f \u043f\u043e\u0434\u0434\u0435\u0440\u0436\u043a\u0430",
        "\u0442\u0435\u0445\u043f\u043e\u0434\u0434\u0435\u0440\u0436",
        "\u0442\u0435\u0445. \u043f\u043e\u0434\u0434\u0435\u0440\u0436",
        "\u0442\u0435\u0445\u043d\u0438\u0447\u0435\u0441\u043a\u043e\u0439 \u043f\u043e\u0434\u0434\u0435\u0440\u0436",
    ],
    "linux": ["linux", "gnu/linux"],
    "\u0437\u043d\u0430\u043d\u0438\u0435 \u0430\u043d\u0433\u043b\u0438\u0439\u0441\u043a\u043e\u0433\u043e": [
        "\u0430\u043d\u0433\u043b\u0438\u0439\u0441\u043a",
        "english",
        "b1",
        "b2",
        "c1",
        "upper-intermediate",
        "advanced english",
    ],
    "advanced": ["advanced"],
    "l1": ["l1", "l 1", "\u043f\u0435\u0440\u0432\u0430\u044f \u043b\u0438\u043d\u0438\u044f", "1 \u043b\u0438\u043d\u0438\u044f", "1-\u044f \u043b\u0438\u043d\u0438\u044f"],
    "l2": ["l2", "l 2", "\u0432\u0442\u043e\u0440\u0430\u044f \u043b\u0438\u043d\u0438\u044f", "2 \u043b\u0438\u043d\u0438\u044f", "2-\u044f \u043b\u0438\u043d\u0438\u044f"],
    "1\u0441": ["1\u0441", "1c"],
    "\u043a\u0430\u0437\u0438\u043d\u043e": ["\u043a\u0430\u0437\u0438\u043d\u043e", "casino", "gambling"],
    "\u043a\u0440\u0438\u043f\u0442\u043e": ["\u043a\u0440\u0438\u043f\u0442\u043e", "crypto", "web3", "blockchain"],
    "php": ["php", "laravel"],
}


def _kw_hit(blob: str, kw: str) -> bool:
    k = _norm_kw(kw)
    if not k:
        return False
    needles = [k] + list(_ALIASES.get(k, []))
    for n in needles:
        if n not in blob:
            continue
        # Ignore negated mentions: "no linux", "без support", "without ..."
        if re.search(
            r"(?:no|without|bez|\u0431\u0435\u0437)\s+" + re.escape(n),
            blob,
        ):
            continue
        return True
    return False


def _remote_early(blob: str, schedule: str) -> Optional[Tuple[int, List[str], bool]]:
    remote_ok = any(
        x in blob
        for x in (
            "\u0443\u0434\u0430\u043b",
            "remote",
            "\u0434\u0438\u0441\u0442\u0430\u043d\u0446",
            "\u043c\u043e\u0436\u043d\u043e \u0443\u0434\u0430\u043b\u0435\u043d\u043d\u043e",
            "\u0444\u043e\u0440\u043c\u0430\u0442 \u0440\u0430\u0431\u043e\u0442\u044b: \u0443\u0434\u0430\u043b",
        )
    )
    office_only = any(
        x in blob for x in ("\u0442\u043e\u043b\u044c\u043a\u043e \u043e\u0444\u0438\u0441", "\u043e\u0444\u0438\u0441\u043d\u0430\u044f", "\u0432 \u043e\u0444\u0438\u0441\u0435")
    ) and not remote_ok
    if office_only or (
        schedule
        and "\u0443\u0434\u0430\u043b" not in schedule.lower()
        and "remote" not in schedule.lower()
        and not remote_ok
    ):
        if "\u0443\u0434\u0430\u043b" in (schedule or "").lower() or "remote" in (schedule or "").lower():
            remote_ok = True
        else:
            return 0, ["\u041d\u0435 \u0443\u0434\u0430\u043b\u0451\u043d\u043a\u0430"], False
    if not remote_ok and "\u0443\u0434\u0430\u043b" not in (schedule or "").lower():
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
        if sal >= good:
            score += 20
            reasons.append(f"+20 ЗП≥{good}")
        elif sal >= floor:
            score += 17
            reasons.append(f"+17 ЗП≥{floor}")
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

    # Missing salary: +20 only if that pushes total to 70%+
    salary_missing_gate = 70
    salary_missing_bonus = 20
    if salary_missing:
        if score + salary_missing_bonus >= salary_missing_gate:
            score += salary_missing_bonus
            reasons.append(
                f"+{salary_missing_bonus} ЗП не указана (дотягивает до {salary_missing_gate}+)"
            )
        else:
            reasons.append(
                f"ЗП не указана / обсуждаемо (без +{salary_missing_bonus}: "
                f"даже с бонусом < {salary_missing_gate})"
            )

    score = max(0, min(100, score))
    return score, reasons, True


def is_salary_negotiable(text: str) -> bool:
    if not text or not str(text).strip():
        return True
    t = str(text).lower()
    return any(
        x in t
        for x in (
            "\u0434\u043e\u0433\u043e\u0432\u043e\u0440",
            "\u043e\u0431\u0441\u0443\u0436\u0434",
            "\u043f\u043e \u0441\u043e\u0431\u0435\u0441\u0435\u0434\u043e\u0432\u0430\u043d",
            "\u043d\u0430 \u0441\u043e\u0431\u0435\u0441\u0435\u0434\u043e\u0432\u0430\u043d",
            "\u043f\u043e \u0440\u0435\u0437\u0443\u043b\u044c\u0442\u0430\u0442\u0430\u043c",
            "\u043d\u0435 \u0443\u043a\u0430\u0437\u0430\u043d",
        )
    )


def parse_salary_max(text: str) -> int | None:
    if not text:
        return None
    if is_salary_negotiable(text) and not re.search(
        r"\d{5,}", text.replace(" ", "").replace("\xa0", "")
    ):
        return None
    t = text.replace("\xa0", " ").replace(" ", "")
    nums = [int(x) for x in re.findall(r"\d{5,7}", t)]
    if not nums:
        nums = [int(x) for x in re.findall(r"\d{3,7}", text.replace("\xa0", "").replace(" ", ""))]
        nums = [n for n in nums if n >= 40000]
    if not nums:
        return None
    return max(nums)


def profile_from_config(cfg: Optional[dict] = None) -> Dict[str, Any]:
    cfg = cfg or {}
    return {
        "must_have_keywords": _as_list(cfg.get("must_have_keywords")),
        "search_keywords": _as_list(cfg.get("search_keywords")),
        "nice_to_have_keywords": _as_list(cfg.get("nice_to_have_keywords")),
        "hard_reject_keywords": _as_list(cfg.get("hard_reject_keywords")),
        "exclude_keywords": _as_list(cfg.get("exclude_keywords")),
    }


def score_vacancy(
    title: str,
    snippet: str = "",
    salary_text: str = "",
    schedule: str = "",
    experience: str = "",
    salary_floor: int = 60000,
    gate_threshold: int = 80,
    profile: Optional[Dict[str, Any]] = None,
) -> Tuple[int, List[str], bool]:
    """Score vacancy by anketa keywords only."""
    gate = int(gate_threshold or 80)
    blob = _text(title, snippet, schedule, experience, salary_text)
    reasons: List[str] = []
    score = 0

    if text_looks_like_refusal(title, snippet):
        return 0, ["HH employer refusal"], False

    early = _remote_early(blob, schedule)
    if early is not None:
        return early
    score += 20
    reasons.append("+20 remote")

    prof = profile_from_config(profile or {})
    must = prof["must_have_keywords"]
    search_kw = prof["search_keywords"]
    nice = prof["nice_to_have_keywords"]
    hard = prof["hard_reject_keywords"]
    excl = prof["exclude_keywords"]

    for kw in hard:
        if _kw_hit(blob, kw):
            return 0, ["hard reject: " + kw], False

    for kw in excl:
        if not _kw_hit(blob, kw):
            continue
        nk = _norm_kw(kw)
        if any(x in nk for x in ("\u043a\u0430\u0437\u0438\u043d\u043e", "\u043a\u0440\u0438\u043f\u0442\u043e", "1\u0441", "1c")):
            return 0, ["exclude reject: " + kw], False
        score -= 30
        reasons.append("-30 exclude:" + kw)

    must_hits = [kw for kw in must if _kw_hit(blob, kw)]
    if must and not must_hits:
        return 10, ["\u041d\u0435\u0442 \u043e\u0431\u044f\u0437\u0430\u0442\u0435\u043b\u044c\u043d\u044b\u0445 \u043c\u0430\u0440\u043a\u0435\u0440\u043e\u0432 (must_have)"], False
    for kw in must_hits:
        score += 25
        reasons.append("+25 must:" + kw)

    must_norm = {_norm_kw(k) for k in must_hits}
    for kw in search_kw:
        if _norm_kw(kw) in must_norm:
            continue
        if _kw_hit(blob, kw):
            score += 10
            reasons.append("+10 search:" + kw)

    for kw in nice:
        if _kw_hit(blob, kw):
            score += 8
            reasons.append("+8 nice:" + kw)

    if any(
        x in blob
        for x in (
            "junior",
            "\u0434\u0436\u0443\u043d",
            "\u0441\u0442\u0430\u0436\u0435\u0440",
            "l1",
            "\u043f\u0435\u0440\u0432\u0430\u044f \u043b\u0438\u043d\u0438\u044f",
        )
    ):
        score += 12
        reasons.append("+12 Junior/L1 fit")
    elif any(
        x in blob
        for x in (
            "senior",
            "\u0441\u0435\u043d\u044c\u043e\u0440",
            "\u0432\u0435\u0434\u0443\u0449\u0438\u0439",
            "lead",
        )
    ):
        score -= 20
        reasons.append("-20 Senior/Lead (~1y)")
    elif any(
        x in blob
        for x in (
            "middle",
            "\u043c\u0438\u0434\u043b",
            "l2",
            "\u0432\u0442\u043e\u0440\u0430\u044f \u043b\u0438\u043d\u0438\u044f",
        )
    ):
        score += 4
        reasons.append("+4 Middle/L2")

    sal = parse_salary_max(salary_text)
    negotiable = sal is None or is_salary_negotiable(salary_text)
    salary_missing = bool(negotiable and sal is None)
    if sal is not None:
        if sal >= salary_floor:
            score += 8
            reasons.append("+8 ZP>=" + str(salary_floor))
        else:
            score -= 12
            reasons.append("-12 ZP low (~" + str(sal) + ")")

    if salary_missing:
        if score + 20 >= gate:
            score += 20
            reasons.append("+20 ZP missing (reaches " + str(gate) + "+)")
        else:
            reasons.append("ZP missing (no +20: still < " + str(gate) + ")")

    score = max(0, min(100, score))
    return score, reasons, True


def explain(score: int, reasons: List[str]) -> str:
    return str(score) + "%\n" + "\n".join(reasons)
