# -*- coding: utf-8 -*-
"""Hard role-sphere gate: drop clearly out-of-sphere vacancies before Cursor.

Three-tier decision:
  PASS    — title clearly names a role matching the sphere; skip heavy checks.
  REJECT  — title clearly names a role that is NOT this sphere; block before Cursor.
  UNCERTAIN — ambiguous (e.g. "Product Manager" for developer sphere);
              pass to Cursor but inject a soft warning in the scoring context.

Public API:
  title_sphere_gate(title, sphere) -> ("pass"|"reject"|"uncertain", reasons)
  hard_reject_out_of_sphere(title, snippet, sphere) -> (bool, reasons)  [legacy]
  build_sphere_prompt_block(sphere, uncertain_title) -> str
  normalize_sphere_category(sphere) -> Optional[str]
"""
from __future__ import annotations

import re
from typing import List, Literal, Optional, Tuple

GateVerdict = Literal["pass", "reject", "uncertain"]

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

# Word-char class for RU/EN token boundaries (avoid «водитель» in «руководитель»).
_W = r"[\w\u0400-\u04ff]"

# Title/snippet patterns that are almost never the listed sphere.
# Matched with token/phrase-aware regex — not naive substring `in`.
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
        "frontend developer",
        "fullstack developer",
        "full stack developer",
        "java developer",
        "golang developer",
        "golang",
        "devops",
        "сисадмин",
        "разработчик",
        "programmer",
        "программист",
        "software engineer",
        "qa engineer",
        "sdet",
        "web developer",
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

# ---------------------------------------------------------------------------
# HARD-PASS patterns — title unambiguously names a developer/dev-adjacent role.
# Matching any of these → immediate PASS regardless of other checks.
# ---------------------------------------------------------------------------
_DEV_TITLE_PASS = re.compile(
    r"(?i)("
    # Classic dev role names
    r"frontend|front[\s-]end|back[\s-]?end|fullstack|full[\s-]?stack|"
    r"разработчик|developer|programmer|программист|"
    r"software\s+engineer|web\s+developer|веб[\s-]разработчик|"
    # Specific stacks that unambiguously mean a dev role
    r"vue[\s.-]?js|react[\s.-]?js|angular[\s.-]?js|"
    r"typescript\s+developer|javascript\s+developer|"
    r"python\s+developer|java\s+developer|golang\s+developer|"
    r"php\s+developer|c\+\+\s+developer|rust\s+developer|"
    r"mobile\s+developer|ios\s+developer|android\s+developer|"
    r"flutter\s+developer|react\s+native\s+developer|"
    # Modern/AI developer titles — vibe-coders, AI devs, etc.
    r"вайб[\s-]?кодер|vibe[\s-]?coder|"
    r"ai\s+developer|ai[\s-]engineer|"
    r"prompt\s+engineer|ml\s+engineer|data\s+engineer|"
    r"llm\s+engineer|nlp\s+engineer|"
    # Tech leads that are clearly dev-side
    r"tech[\s-]?lead\b|technical\s+lead|"
    r"lead\s+(frontend|backend|developer|разработ)|"
    r"senior\s+(frontend|backend|developer|разработчик|engineer)|"
    r"middle\s+(frontend|backend|developer|разработчик)|"
    r"junior\s+(frontend|backend|developer|разработчик)|"
    # Infra/platform devs
    r"devops\s+engineer|platform\s+engineer|sre\s+engineer|site\s+reliability"
    r")"
)

# ---------------------------------------------------------------------------
# MANAGER as the PRIMARY role — without a dev qualifier.
# If matched AND no _DEV_POSITIVE in the same title → REJECT for developer sphere.
# If matched AND _DEV_POSITIVE → UNCERTAIN (product manager, tech manager, etc.)
# ---------------------------------------------------------------------------
_MANAGER_PRIMARY = re.compile(
    r"(?i)\b("
    # "менеджер по X" — almost always non-dev
    r"менеджер\s+по\s+(продажам|работе\s+с|привлечению|развитию\s+продаж|"
    r"персоналу|кадрам|закупкам|снабжению)|"
    # Pure manager titles
    r"операционный\s+менеджер|"
    r"проектный\s+менеджер|"
    r"офис[\s-]?менеджер|office\s+manager|"
    r"бренд[\s-]?менеджер|brand\s+manager|"
    r"контент[\s-]?менеджер|content\s+manager|"
    r"event\s+manager|"
    # Sales variants
    r"account\s+manager|key\s+account|"
    r"sales\s+manager|sales\s+executive|"
    r"менеджер\s+продаж\b|"
    # Руководитель clearly non-dev
    r"руководитель\s+(продаж|направления\s+продаж|отдела\s+продаж|"
    r"офиса|административного|склада)|"
    # HR / recruitment
    r"hr[\s-]?менеджер|hr\s+manager|менеджер\s+по\s+подбору|"
    r"рекрутинг[\s-]?менеджер"
    r")\b"
)

# Titles where "менеджер/manager/руководитель" is present but there's a DEV qualifier.
# These should be UNCERTAIN (not hard-reject) for developer sphere.
_DEV_MANAGER_QUALIFIER = re.compile(
    r"(?i)\b("
    r"product\s+manager|продуктовый\s+менеджер|менеджер\s+продукта|"
    r"project\s+manager|менеджер\s+проекта|руководитель\s+проекта|"
    r"engineering\s+manager|технический\s+менеджер|"
    r"delivery\s+manager|"
    r"scrum\s+master|agile\s+coach|"
    r"руководитель\s+(разработки|технического|it[\s-]?отдела|команды\s+разработ)|"
    r"head\s+of\s+(frontend|backend|development|engineering|product)|"
    r"вице[\s-]?президент\s+по\s+технологиям|cto\b|vp\s+engineering"
    r")\b"
)

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

_DESIGN_POSITIVE = re.compile(
    r"(?i)("
    r"дизайнер|designer|illustrator|иллюстратор|"
    r"ui/?ux|ux/?ui|figma|product\s+designer|"
    r"графическ|инфографик|visual\s+design|art\s+director|"
    r"motion\s+design|web\s+designer|digital\s+designer"
    r")"
)

_DEV_ROLE_FOR_DESIGNER = re.compile(
    r"(?i)("
    r"frontend|backend|fullstack|full[\s-]?stack|"
    r"разработчик|programmer|программист|"
    r"golang|java\s+developer|devops|qa\s+engineer|sdet|"
    r"software\s+engineer|web\s+developer|"
    r"team\s+lead\s+(frontend|backend|fullstack|разработ)|"
    r"lead\s+(frontend|backend|developer|разработ)|"
    r"руководитель\s+разработ"
    r")"
)

# Primary-role sales/SMM tokens checked against developer titles (token-aware).
_DEV_SALES_BLOCK = (
    "менеджер по продажам",
    "sales manager",
    "smm",
    "маркетолог",
    "рекрутер",
    "бухгалтер",
)


def _title_matches_pattern(pat: str, title_l: str) -> bool:
    """Match OUT_OF_SPHERE pattern with word/phrase boundaries."""
    p = str(pat or "").strip().lower()
    if not p:
        return False
    if " " in p or re.search(r"[\s-]", p):
        parts = [part for part in re.split(r"[\s-]+", p) if part]
        if not parts:
            return False
        inner = r"[\s-]+".join(re.escape(part) for part in parts)
        rx = rf"(?<!{_W}){inner}(?!{_W})"
    else:
        rx = rf"(?<!{_W}){re.escape(p)}(?!{_W})"
    return re.search(rx, title_l, re.IGNORECASE) is not None


def title_sphere_gate(
    title: str,
    sphere: str,
    snippet: str = "",
) -> Tuple[GateVerdict, List[str]]:
    """Three-tier title gate.

    Returns:
        ("pass", reasons)      — title clearly matches sphere; skip heavy checks.
        ("reject", reasons)    — title clearly mismatches; block before Cursor.
        ("uncertain", reasons) — ambiguous; pass to Cursor with a soft warning.

    ``sphere`` is the user-declared sphere string (free text).
    """
    raw = str(sphere or "").strip()
    cat = normalize_sphere_category(raw) if raw else None
    title_l = str(title or "").strip().lower()

    if not title_l:
        return "uncertain", ["gate:empty-title"]

    # ------------------------------------------------------------------
    # HARD PASS: title unambiguously names a role matching this sphere.
    # Only for "developer" category for now; other spheres rely on legacy path.
    # ------------------------------------------------------------------
    if cat == "developer" and _DEV_TITLE_PASS.search(title_l):
        return "pass", ["gate:dev-title-match"]

    # ------------------------------------------------------------------
    # HARD REJECT via legacy logic (reuse existing function).
    # ------------------------------------------------------------------
    rejected, reasons = hard_reject_out_of_sphere(title, snippet, sphere)
    if rejected:
        return "reject", reasons

    # ------------------------------------------------------------------
    # Extra developer-sphere checks not covered by legacy code.
    # ------------------------------------------------------------------
    if cat == "developer":
        # Primary manager role WITHOUT dev qualifier → reject.
        if _MANAGER_PRIMARY.search(title_l):
            if not _DEV_POSITIVE.search(title_l):
                return "reject", ["gate:manager-primary-no-dev-signal"]

        # Dev-qualified manager / PM / Scrum → UNCERTAIN.
        if _DEV_MANAGER_QUALIFIER.search(title_l):
            return "uncertain", ["gate:dev-manager-role"]

        # Generic "менеджер" or "manager" without any qualifier — UNCERTAIN.
        # Catches: "Менеджер", "IT-менеджер", "Digital manager", etc.
        bare_manager = re.search(r"(?i)\bменеджер\b|\bmanager\b", title_l)
        if bare_manager and not _DEV_POSITIVE.search(title_l):
            # Already handled MANAGER_PRIMARY above (→ reject).
            # What's left is ambiguous "менеджер IT" type titles.
            return "uncertain", ["gate:bare-manager-title"]

        # Bare "руководитель" without dev context → UNCERTAIN.
        bare_head = re.search(r"(?i)\bруководитель\b", title_l)
        if bare_head and not re.search(
            r"(?i)(разработ|технич|it[\s-]|software|engineering|frontend|backend|"
            r"digital|продукт|product)",
            title_l,
        ):
            return "uncertain", ["gate:bare-head-title"]

    # ------------------------------------------------------------------
    # Default: no strong signal either way.
    # ------------------------------------------------------------------
    return "uncertain", ["gate:no-strong-signal"]


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


def build_sphere_prompt_block(
    sphere: str = "",
    uncertain_title: str = "",
    uncertain_reasons: Optional[List[str]] = None,
) -> str:
    """Text for Cursor scoringRules / candidate context.

    Args:
        sphere: user-declared sphere string.
        uncertain_title: if the title gate returned "uncertain", pass the title
            here to inject a soft confirmation warning into the Cursor prompt.
        uncertain_reasons: gate reasons list (for debug annotation).
    """
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

    ut = str(uncertain_title or "").strip()
    if ut:
        reason_str = (
            f" [reasons: {', '.join(uncertain_reasons)}]"
            if uncertain_reasons
            else ""
        )
        lines += [
            "",
            "## ⚠️ Title ambiguity — confirm before scoring",
            f"The vacancy title **«{ut}»** did not clearly match the declared sphere{reason_str}.",
            "Before assigning a high score, explicitly verify in the vacancy body that this "
            f"role requires genuine «{raw}» skills (e.g. coding, building, engineering).",
            "If the role is primarily non-technical management, sales, or coordination "
            "without engineering work — score low (≤25) and set accept=false.",
        ]

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
        if not _title_matches_pattern(pat, title_l):
            continue
        # Designer exception: clear design role wins over dev-ish noise words.
        if cat == "designer" and _DESIGN_POSITIVE.search(title_l):
            continue
        # Developer exception: "Frontend" in title wins over weak marketing words in title
        if cat == "developer" and _DEV_POSITIVE.search(title_l):
            # still reject if sales/smm/маркетолог is the primary role word
            if any(_title_matches_pattern(x, title_l) for x in _DEV_SALES_BLOCK):
                return True, [f"sphere-reject:{pat}"]
            continue
        return True, [f"sphere-reject:{pat}"]

    # Designer: pure software-dev titles without any design signal
    if cat == "designer":
        if _DEV_ROLE_FOR_DESIGNER.search(title_l) and not _DESIGN_POSITIVE.search(title_l):
            return True, ["sphere-reject:dev-title-for-designer"]

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
