# -*- coding: utf-8 -*-
"""Hard role-sphere gate: drop clearly out-of-sphere vacancies before Cursor.

Soft layer (Cursor prompt) lives in scoring_context / candidate block.
This module is the cheap Python pre-filter on title (+ short snippet).
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

# Normalized sphere category → aliases the user may type in Settings.
SPHERE_ALIASES = {
    "developer": (
        "разработчик",
        "developer",
        "programmer",
        "программист",
        "frontend",
        "backend",
        "fullstack",
        "full-stack",
        "full stack",
        "инженер-программист",
        "software engineer",
        "web developer",
        "vue",
        "react",
        "angular",
        "dev",
    ),
    "designer": (
        "дизайнер",
        "designer",
        "ui/ux",
        "ux/ui",
        "ui designer",
        "ux designer",
        "product designer",
        "графический дизайнер",
    ),
    "qa": (
        "qa",
        "тестировщик",
        "tester",
        "quality assurance",
        "qa engineer",
        "sdet",
        "автотестировщик",
    ),
    "analyst": (
        "аналитик",
        "analyst",
        "системный аналитик",
        "бизнес-аналитик",
        "product analyst",
        "data analyst",
    ),
    "devops": (
        "devops",
        "sre",
        "platform engineer",
        "инфраструктур",
        "site reliability",
    ),
    "pm": (
        "project manager",
        "product manager",
        "руководитель проекта",
        "проджект",
        "продакт менеджер",
        "product owner",
    ),
    "support": (
        "техподдержк",
        "technical support",
        "support engineer",
        "helpdesk",
        "help desk",
        "специалист поддержки",
    ),
}

# Title/snippet patterns that are almost never the listed sphere.
# Matched case-insensitively as substrings (simple + fast).
OUT_OF_SPHERE_TITLE: dict[str, Tuple[str, ...]] = {
    "developer": (
        "менеджер по продажам",
        "менеджер продаж",
        "sales manager",
        "account manager",
        "key account",
        "менеджер по работе с клиентами",
        "менеджер по привлечению",
        "менеджер по развитию продаж",
        "sales executive",
        "smm",
        "смм",
        "маркетолог",
        "marketing manager",
        "digital marketing",
        "контент-менеджер",
        "content manager",
        "бренд-менеджер",
        "brand manager",
        "рекрутер",
        "recruiter",
        "hr manager",
        "hr-менеджер",
        "hr менеджер",
        "специалист по кадрам",
        "менеджер по персоналу",
        "бухгалтер",
        "accountant",
        "юрист",
        "lawyer",
        "оператор call",
        "оператор колл",
        "call-центр",
        "call центр",
        "телемаркетолог",
        "риелтор",
        "риэлтор",
        "курьер",
        "водитель",
        "повар",
        "официант",
        "продавец-консультант",
        "кассир",
        "мерчандайзер",
        "торговый представитель",
        "менеджер маркетплейс",
        "менеджер wildberries",
        "менеджер ozon",
        "ассистент руководителя",
        "офис-менеджер",
        "office manager",
        "администратор салона",
        "медсестра",
        "врач ",
    ),
    "designer": (
        "менеджер по продажам",
        "sales manager",
        "рекрутер",
        "бухгалтер",
        "водитель",
        "повар",
        "backend developer",
        "java developer",
        "golang",
        "devops",
        "сисадмин",
    ),
    "qa": (
        "менеджер по продажам",
        "sales manager",
        "smm",
        "маркетолог",
        "рекрутер",
        "бухгалтер",
        "водитель",
        "повар",
    ),
    "analyst": (
        "менеджер по продажам",
        "sales manager",
        "smm",
        "рекрутер",
        "водитель",
        "повар",
        "официант",
    ),
    "devops": (
        "менеджер по продажам",
        "sales manager",
        "smm",
        "маркетолог",
        "рекрутер",
        "бухгалтер",
        "дизайнер интерьера",
    ),
    "pm": (
        "менеджер по продажам",
        "sales manager",
        "smm-менеджер",
        "телемаркетолог",
        "бухгалтер",
        "водитель",
        "повар",
    ),
    "support": (
        "менеджер по продажам",
        "sales manager",
        "smm",
        "маркетолог",
        "рекрутер",
        "бухгалтер",
        "водитель",
        "повар",
    ),
}

# Extra: role titles that look like pure sales even with "AI/product" fluff.
_SALESY_TITLE = re.compile(
    r"(?i)\b("
    r"менеджер\s+по\s+продажам|"
    r"менеджер\s+продаж|"
    r"sales\s+manager|"
    r"account\s+manager|"
    r"менеджер\s+по\s+работе\s+с\s+клиентами|"
    r"менеджер\s+по\s+привлечению|"
    r"торговый\s+представитель|"
    r"специалист\s+по\s+продажам"
    r")\b"
)

_DEV_POSITIVE = re.compile(
    r"(?i)("
    r"developer|разработчик|программист|frontend|backend|fullstack|"
    r"full[\s-]?stack|engineer|инженер\s*ПО|vue|react|angular|typescript|"
    r"javascript|python|java\b|golang|c\+\+|php\s*developer|qa\s*engineer|"
    r"devops|sre|analyst|аналитик|designer|дизайнер"
    r")"
)


def normalize_sphere_category(sphere: str) -> Optional[str]:
    """Map free-text sphere to a known category, or None if unknown."""
    s = str(sphere or "").strip().lower()
    if not s:
        return None
    for cat, aliases in SPHERE_ALIASES.items():
        for a in aliases:
            if a in s:
                return cat
    return None


def build_sphere_prompt_block(sphere: str = "") -> str:
    """Text for Cursor scoringRules / candidate context."""
    raw = str(sphere or "").strip()
    if not raw:
        return ""
    cat = normalize_sphere_category(raw)
    lines = [
        "## Target activity sphere (hard intent)",
        f"User-declared sphere: **{raw}**.",
        "Score ONLY vacancies that are genuinely this kind of role.",
        "Sales, SMM, marketing, recruiting, HR, accounting, courier, driver, "
        "cook, marketplace manager (non-dev), call-center — are NOT a fit "
        f"for «{raw}» unless the vacancy is clearly a technical/engineering role "
        "in that domain (rare). Prefer accept=false and low score for clear mismatches.",
    ]
    if cat:
        lines.append(f"Normalized category for filters: `{cat}`.")
    return "\n".join(lines)


def hard_reject_out_of_sphere(
    title: str,
    snippet: str = "",
    sphere: str = "",
) -> Tuple[bool, List[str]]:
    """Return (rejected, reasons) if vacancy is clearly outside declared sphere.

    Uses title primarily; snippet only as weak extra context for salesy patterns.
    If sphere is empty or unrecognized → no reject (do not invent).
    """
    raw = str(sphere or "").strip()
    if not raw:
        return False, []

    cat = normalize_sphere_category(raw)
    title_l = str(title or "").lower()
    hay = f"{title_l}\n{str(snippet or '')[:500].lower()}"

    # Universal: blatant sales titles are out for developer/designer/qa/devops/analyst
    if cat in ("developer", "designer", "qa", "devops", "analyst", "support"):
        if _SALESY_TITLE.search(title_l):
            # Exception: title also strongly signals engineering
            if cat == "developer" and _DEV_POSITIVE.search(title_l):
                # e.g. "Sales Engineer" / "Developer Relations" — let Cursor decide
                if not re.search(r"(?i)sales\s+engineer|developer\s+advocate|devrel", title_l):
                    if re.search(r"(?i)менеджер\s+по\s+продажам|sales\s+manager", title_l):
                        return True, ["sphere-reject:sales-title"]
            else:
                return True, ["sphere-reject:sales-title"]

    if not cat:
        # Unknown sphere: only block pure sales/SMM when sphere text looks tech-ish
        if re.search(r"(?i)разраб|develop|програм|engineer|qa|дизайн|design", raw):
            if _SALESY_TITLE.search(title_l) or "smm" in title_l or "маркетолог" in title_l:
                if not _DEV_POSITIVE.search(title_l):
                    return True, ["sphere-reject:non-tech-title"]
        return False, []

    patterns = OUT_OF_SPHERE_TITLE.get(cat) or ()
    for pat in patterns:
        if pat in title_l:
            # Developer exception: "Frontend" in title wins over weak marketing words in title
            if cat == "developer" and _DEV_POSITIVE.search(title_l):
                # still reject if sales/smm/маркетолог is the primary role word
                if any(
                    x in title_l
                    for x in (
                        "менеджер по продажам",
                        "sales manager",
                        "smm",
                        "маркетолог",
                        "рекрутер",
                        "бухгалтер",
                    )
                ):
                    return True, [f"sphere-reject:{pat}"]
                continue
            return True, [f"sphere-reject:{pat}"]

    # Developer: marketplace operator / call-center without any tech signal
    if cat == "developer":
        if re.search(
            r"(?i)(менеджер\s+(wb|wildberries|ozon|маркетплейс)|"
            r"специалист\s+поддержки\s+маркет|"
            r"оператор\s+(call|колл)|"
            r"ассистент\s+руководителя)",
            title_l,
        ) and not _DEV_POSITIVE.search(title_l):
            return True, ["sphere-reject:non-dev-ops"]

    # Weak snippet-only matches are intentionally NOT used — too many false positives.
    _ = hay
    return False, []
