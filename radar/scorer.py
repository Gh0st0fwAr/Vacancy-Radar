# -*- coding: utf-8 -*-
"""Profile-only rule scoring (python-only branch). No Vue legacy."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .refusal import text_looks_like_refusal


def _text(*parts: str) -> str:
    return " ".join(p or "" for p in parts).lower().replace("\u0451", "\u0435")


def _norm_kw(s: str) -> str:
    return (s or "").strip().lower().replace("\u0451", "\u0435")


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
    "карточки маркетплейсов": [
        "карточки маркетплейс",
        "карточек на маркетплейс",
        "карточек товар",
        "карточка товар",
        "дизайнер карточек",
        "инфографик",
        "маркетплейс",
        "wildberries",
        "вайлдберриз",
        "ozon",
        "озон",
        "графический дизайнер",
        "графического дизайнер",
        "предпечат",
        "логотип",
        "фирменный стиль",
    ],
    "графический дизайнер": [
        "графический дизайнер",
        "графического дизайнер",
        "графический дизайн",
    ],
    "дизайнер инфографики": [
        "дизайнер инфографики",
        "инфографики для маркетплейс",
        "инфографика для маркетплейс",
        "инфографик",
    ],
    "photoshop": ["photoshop", "фотошоп"],
    "illustrator": ["illustrator"],
    "coreldraw": ["coreldraw", "corel draw", "corel"],
    "figma": ["figma"],
    "chatgpt": ["chatgpt", "chat gpt"],
    "нейронные сети": ["нейронн", "нейросет"],
    "rich-контент": ["rich-контент", "rich контент", "rich content"],
    "a/b тесты карточки": ["a/b", "а/в", "ab-тест", "аб-тест", "a/b тест"],
    "баннеры": ["баннер"],
    "веб-дизайнер": [
        "веб-дизайнер",
        "веб дизайнер",
        "web-дизайнер",
        "web дизайнер",
        "web designer",
        "ui/ux",
        "ux/ui",
        "ux-дизайнер",
        "ui-дизайнер",
    ],
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
            return 0, ["\u0424\u043e\u0440\u043c\u0430\u0442 \u043d\u0435 remote"], False
    return None


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


def _as_bool(val: Any, default: bool = False) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() not in ("0", "false", "no", "off", "")


def _as_score_map(val: Any) -> Dict[str, int]:
    if not val:
        return {}
    if isinstance(val, dict):
        out: Dict[str, int] = {}
        for k, v in val.items():
            key = str(k).strip()
            if not key:
                continue
            try:
                out[key] = int(v)
            except (TypeError, ValueError):
                continue
        return out
    return {}


def _layer_score(text: str, mapping: Dict[str, int], cap: int, prefix: str) -> Tuple[int, List[str]]:
    if not mapping:
        return 0, []
    blob = _text(text)
    pos = 0
    neg = 0
    reasons: List[str] = []
    for kw, w in mapping.items():
        if not _kw_hit(blob, kw):
            continue
        if w >= 0:
            pos += w
            reasons.append(f"+{w} {prefix}:{kw}")
        else:
            neg += w
            reasons.append(f"{w} {prefix}:{kw}")
    if cap > 0 and pos > cap:
        reasons.append(f"cap {prefix} {pos}->{cap}")
        pos = cap
    return pos + neg, reasons


def _spb_office_only(blob: str, remote_ok: bool) -> bool:
    if remote_ok:
        return False
    moscow = any(x in blob for x in ("москв", "мск"))
    spb = any(
        x in blob
        for x in (
            "санкт-петербург",
            "санкт петербург",
            "г. спб",
            "спб,",
            "петербург",
        )
    )
    return spb and not moscow


def profile_from_config(cfg: Optional[dict] = None) -> Dict[str, Any]:
    cfg = cfg or {}
    return {
        "must_have_keywords": _as_list(cfg.get("must_have_keywords")),
        "search_keywords": _as_list(cfg.get("search_keywords")),
        "nice_to_have_keywords": _as_list(cfg.get("nice_to_have_keywords")),
        "hard_reject_keywords": _as_list(cfg.get("hard_reject_keywords")),
        "exclude_keywords": _as_list(cfg.get("exclude_keywords")),
        "require_remote": cfg.get("require_remote", True),
        "skip_level_heuristic": _as_bool(cfg.get("skip_level_heuristic"), False),
        "score_title": _as_score_map(cfg.get("score_title")),
        "score_body": _as_score_map(cfg.get("score_body")),
        "score_skills": _as_score_map(cfg.get("score_skills")),
        "title_score_cap": int(cfg.get("title_score_cap") or 22),
        "body_score_cap": int(cfg.get("body_score_cap") or 18),
        "skill_score_cap": int(cfg.get("skill_score_cap") or 16),
        "format_base": int(cfg.get("format_base") or 20),
        "format_remote_bonus": int(cfg.get("format_remote_bonus") or 0),
        "must_have_pts": int(cfg.get("must_have_pts") or 25),
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

    prof = profile_from_config(profile or {})
    must = prof["must_have_keywords"]
    search_kw = prof["search_keywords"]
    nice = prof["nice_to_have_keywords"]
    hard = prof["hard_reject_keywords"]
    excl = prof["exclude_keywords"]
    layered = bool(prof["score_title"] or prof["score_body"] or prof["score_skills"])
    require_remote = _as_bool(prof.get("require_remote"), True)

    remote_ok = any(
        x in blob
        for x in (
            "удал",
            "remote",
            "дистанц",
            "можно удаленно",
            "формат работы: удален",
        )
    )
    if "удал" in (schedule or "").lower() or "remote" in (schedule or "").lower():
        remote_ok = True

    if require_remote:
        early = _remote_early(blob, schedule)
        if early is not None:
            return early
        score += 20
        reasons.append("+20 remote")
    else:
        if _spb_office_only(blob, remote_ok):
            return 0, ["Офис не Москва"], False
        fmt = int(prof["format_base"] or 12)
        score += fmt
        reasons.append(f"+{fmt} format ok")
        extra = int(prof["format_remote_bonus"] or 0)
        if extra and remote_ok:
            score += extra
            reasons.append(f"+{extra} remote")

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
        return 10, ["Нет обязательных маркеров (must_have)"], False
    must_pts = int(prof["must_have_pts"] or 25)
    for kw in must_hits:
        score += must_pts
        reasons.append(f"+{must_pts} must:{kw}")

    if layered:
        t_pts, t_rs = _layer_score(title, prof["score_title"], int(prof["title_score_cap"] or 22), "title")
        b_pts, b_rs = _layer_score(snippet, prof["score_body"], int(prof["body_score_cap"] or 18), "body")
        s_pts, s_rs = _layer_score(blob, prof["score_skills"], int(prof["skill_score_cap"] or 16), "skill")
        score += t_pts + b_pts + s_pts
        reasons.extend(t_rs + b_rs + s_rs)
    else:
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

    if not prof["skip_level_heuristic"]:
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
        good = 0
        mid = 0
        if isinstance(profile, dict):
            try:
                good = int(profile.get("salary_good") or 0)
            except (TypeError, ValueError):
                good = 0
            try:
                mid = int(profile.get("salary_mid") or 0)
            except (TypeError, ValueError):
                mid = 0
        if layered and good and sal >= good:
            score += 8
            reasons.append("+8 ZP>=" + str(good))
        elif layered and mid and sal >= mid:
            score += 6
            reasons.append("+6 ZP>=" + str(mid))
        elif sal >= salary_floor:
            pts = 2 if layered else 8
            score += pts
            reasons.append(f"+{pts} ZP>=" + str(salary_floor))
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
