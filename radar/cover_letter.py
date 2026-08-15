# -*- coding: utf-8 -*-
"""Сопроводительные письма: Cursor SDK (основной путь) + локальная адаптация."""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .config import ROOT, load_config

BRIDGE = ROOT / "cursor_bridge" / "generate_letter.mjs"
RULES_CWD = Path(r"G:\Лёха уроки")

HEADER = (
    "Портфолио: https://gh0st0fwar.github.io/\n"
    "Telegram: @daniil_virin\n"
    "Email: 39dv@mail.ru\n"
)

# Маркер старого тупого шаблона — чтобы пересобрать уже лежащие в очереди.
STALE_MARKERS = (
    "Основная специализация — сложные SPA и data-heavy интерфейсы: дашборды, "
    "конфигурационные таблицы, карты, real-time телеметрия, генераторы форм.",
)


def make_cover_letter(
    vacancy_title: str,
    *,
    company: str = "",
    description: str = "",
    salary: str = "",
    reasons: Optional[Sequence[str]] = None,
    force_local: bool = False,
) -> Tuple[str, str]:
    """
    Возвращает (письмо, источник).
    источник: "cursor" | "local"
    """
    title = (vacancy_title or "Frontend").strip()
    company = (company or "").strip()
    description = (description or "").strip()
    salary = (salary or "").strip()
    reasons_list = list(reasons or [])

    cfg = load_config()
    use_cursor = bool(cfg.get("cover_letter_via_cursor", True)) and not force_local
    if use_cursor:
        letter = _via_cursor(
            title=title,
            company=company,
            description=description,
            salary=salary,
            reasons=reasons_list,
            cfg=cfg,
        )
        if letter:
            return letter, "cursor"

    return (
        _via_local(
            title=title,
            company=company,
            description=description,
            salary=salary,
            reasons=reasons_list,
        ),
        "local",
    )


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
) -> Optional[str]:
    if not BRIDGE.exists():
        return None
    key = _api_key(cfg)
    if not key:
        return None

    payload = {
        "title": title,
        "company": company,
        "description": description,
        "salary": salary,
        "reasons": reasons,
        "apiKey": key,
        "model": cfg.get("cursor_model") or "composer-2.5",
        "cwd": str(RULES_CWD),
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
            err = (proc.stderr or proc.stdout or "").strip().splitlines()
            raise RuntimeError(err[0] if err else f"cursor bridge exit {proc.returncode}")

        letter = (proc.stdout or "").strip()
        if len(letter) < 200 or "Портфолио:" not in letter:
            raise RuntimeError("Cursor вернул пустое/битое письмо")
        return _sanitize(letter)
    except Exception:
        return None


def _sanitize(letter: str) -> str:
    text = letter.strip()
    # Убрать markdown-ограждения и случайную мету
    text = re.sub(r"^```[\w]*\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    lines = []
    for line in text.splitlines():
        low = line.lower().strip()
        if low.startswith("ссылка на вакансию"):
            continue
        if re.match(r"^https?://.*(hh\.ru|getmatch|habr|remote-job)", low):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


# ---- локальная адаптация (не один шаблон: набор блоков под темы вакансии) ----


def _norm(s: str) -> str:
    return (s or "").lower().replace("ё", "е")


def _detect_themes(title: str, description: str, reasons: Sequence[str]) -> List[str]:
    blob = _norm(f"{title}\n{description}\n{' '.join(reasons)}")
    themes: List[str] = []

    def has(*needles: str) -> bool:
        return any(n in blob for n in needles)

    if has("nuxt"):
        themes.append("nuxt")
    if has("vue 2", "vue2", "vuex"):
        themes.append("vue2")
    if has("vue 3", "vue3", "composition api", "script setup"):
        themes.append("vue3")
    if has("pinia"):
        themes.append("pinia")
    if has("typescript", " type script", " ts ", "на ts"):
        themes.append("typescript")
    if has("карт", "leaflet", "mapbox", "яндex.карт", "yandex map", "gis"):
        themes.append("maps")
    if has("дашборд", "dashboard", "график", "chart", "телеметр", "монитор"):
        themes.append("dashboard")
    if has("таблиц", "ag-grid", "agrid", "data-grid", "виртуализ"):
        themes.append("tables")
    if has("форм", "form generator", "динамическ"):
        themes.append("forms")
    if has("websocket", "web socket", "real-time", "realtime", "сокет"):
        themes.append("realtime")
    if has("fullstack", "full stack", "full-stack", "бэкенд", "backend", "node.js", "nestjs"):
        themes.append("fullstack")
    if has("ux/ui", "ui/ux", "дизайн-систем", "figma", "pixel"):
        themes.append("ux")
    if has("легаси", "legacy", "рефактор", "миграц"):
        themes.append("legacy")
    if has("scss", "sass", "css modules", "tailwind"):
        themes.append("styles")
    if has("spa") or not themes:
        themes.append("spa")

    # уникальный порядок, сохраняя приоритет
    seen = set()
    out = []
    for t in themes:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:6]


_BLOCKS: Dict[str, str] = {
    "vue3": (
        "Уверенно работаю с Vue 3 (Composition API, script setup), TypeScript, "
        "слоем состояния и роутингом — как раз тот контур, который обычно нужен "
        "в продуктовых SPA."
    ),
    "vue2": (
        "В проде глубоко знаю Vue 2 и Vuex: поддержка легаси, аккуратные доработки "
        "и поэтапный перевод модулей на более современный стек без «большого взрыва»."
    ),
    "nuxt": (
        "С Nuxt работаю на уровне Junior / активного роста (SSR, Nitro API, "
        "file-based routing) — без завышения, готов быстро добирать практику в бою."
    ),
    "pinia": (
        "Для состояния привычен Pinia: понятные сторы, предсказуемые обновления UI "
        "и нормальная декомпозиция сложных экранов."
    ),
    "typescript": (
        "TypeScript для меня рабочий язык фронта: типы на границах API, меньше "
        "сюрпризов в больших формах и таблицах."
    ),
    "maps": (
        "Есть коммерческий опыт с картографией и геоданными в UI: тяжёлые карты, "
        "оверлеи, связка карта ↔ таблицы/фильтры без деградации отзывчивости."
    ),
    "dashboard": (
        "Сильная сторона — data-heavy интерфейсы: дашборды, мониторинг, телеметрия, "
        "графики и экраны, где много живых данных и важна стабильность в проде."
    ),
    "tables": (
        "Уверенно делаю сложные таблицы и конфигурационные гриды: фильтры, "
        "иерархия, виртуализация, аккуратная работа с большими объёмами строк."
    ),
    "forms": (
        "Делал генераторы и сложные формы по схемам API: валидация, динамические "
        "поля, предсказуемое поведение на длинных пользовательских сценариях."
    ),
    "realtime": (
        "Понимаю real-time контуры на фронте: обновления по событиям, аккуратный "
        "рендер и состояние, чтобы экран не «трясся» на частых апдейтах."
    ),
    "fullstack": (
        "По fullstack честно: мой сильный край — frontend на Vue. Backend/Node "
        "готов добирать по задаче, не притворяясь senior full-stack."
    ),
    "ux": (
        "Близки задачи на стыке UI и инженерии: аккуратная вёрстка, понятные "
        "состояния интерфейса, работа с макетами без потери технической глубины."
    ),
    "legacy": (
        "Умею жить в легаси: точечный рефакторинг, снижение риска регрессий, "
        "перенос кусков на Vue 3 + TS по мере ценности для продукта."
    ),
    "styles": (
        "Вёрстку держу в боевом виде: SCSS/современный CSS, адаптив, аккуратные "
        "компоненты без расползания стилей."
    ),
    "spa": (
        "Основной профиль — сложные SPA: архитектура экранов, REST-интеграции, "
        "оптимизация тяжёлых страниц (lazy-load, code splitting, виртуализация)."
    ),
}


def _nms_anchor(themes: Sequence[str]) -> str:
    bits = []
    if "maps" in themes:
        bits.append("карты")
    if "dashboard" in themes:
        bits.append("дашборды/телеметрия")
    if "tables" in themes:
        bits.append("тяжёлые таблицы")
    if "forms" in themes:
        bits.append("генераторы форм")
    if not bits:
        bits = ["data-heavy экраны", "интеграции с API"]
    focus = ", ".join(bits[:3])
    return (
        "В коммерции проектировал и развивал enterprise NMS для телеком-сетей "
        f"(~90+ компонентов): как раз профиль, где важны {focus}, стабильный "
        "продакшен и умение доводить фичи до конца."
    )


def _fit_sentence(title: str, company: str, themes: Sequence[str]) -> str:
    company_bit = f" в {company}" if company else ""
    if "nuxt" in themes:
        angle = "интересны SSR/Nuxt-задачи рядом с сильным Vue-ядром"
    elif "fullstack" in themes:
        angle = "готов закрывать frontend-контур и честно усиливать смежные зоны"
    elif "ux" in themes:
        angle = "близка инженерия интерфейсов с вниманием к UX"
    elif "maps" in themes or "dashboard" in themes:
        angle = "хорошо ложится на мой опыт data-heavy / мониторинговых UI"
    else:
        angle = "по стеку и уровню задач выглядит близко к моему коммерческому опыту"
    return f"Вакансия «{title}»{company_bit} {angle}."


def _via_local(
    *,
    title: str,
    company: str,
    description: str,
    salary: str,
    reasons: Sequence[str],
) -> str:
    themes = _detect_themes(title, description, reasons)
    # 3 тематических блока + якорь NMS + fit — комбинация зависит от вакансии
    body_blocks = []
    for key in themes:
        if key in _BLOCKS and key not in ("spa",):
            body_blocks.append(_BLOCKS[key])
        if len(body_blocks) >= 3:
            break
    if len(body_blocks) < 2:
        body_blocks.append(_BLOCKS["spa"])
    if "nuxt" in themes and _BLOCKS["nuxt"] not in body_blocks:
        body_blocks.append(_BLOCKS["nuxt"])

    intro = (
        f"Я Middle frontend-разработчик с 6+ годами коммерческого опыта на Vue. "
        f"{_fit_sentence(title, company, themes)}"
    )

    parts = [
        HEADER.rstrip(),
        "",
        "Здравствуйте!",
        f"Заинтересовала ваша вакансия {title}.",
        "",
        intro,
        "",
        " ".join(body_blocks[:3]),
        "",
        _nms_anchor(themes),
        "",
    ]
    if "nuxt" not in themes:
        parts.append(_BLOCKS["nuxt"])
        parts.append("")

    salary_note = ""
    if salary:
        salary_note = f" В карточке указано: {salary}."
    parts.append(
        "Ищу удалённую работу. Ориентир по компенсации ~160k на руки, "
        f"до ~200k обсуждаемо.{salary_note}"
    )
    parts.append("")
    parts.append(
        "Буду рад кратко созвониться или ответить на вопросы по опыту и проектам. "
        "Актуальные демо и код — в портфолио по ссылке выше."
    )
    return _sanitize("\n".join(parts))
