# -*- coding: utf-8 -*-
"""Detect HH employer refusal markers in page/queue text."""
from __future__ import annotations

from typing import Any

REFUSAL_MARKERS = (
    "\u0432\u0430\u043c \u043e\u0442\u043a\u0430\u0437\u0430\u043b\u0438",
    "\u043e\u0442\u043a\u043b\u0438\u043a \u043e\u0442\u043a\u043b\u043e\u043d\u0451\u043d",
    "\u043e\u0442\u043a\u043b\u0438\u043a \u043e\u0442\u043a\u043b\u043e\u043d\u0435\u043d",
    "\u043e\u0442\u043a\u0430\u0437 \u0440\u0430\u0431\u043e\u0442\u043e\u0434\u0430\u0442\u0435\u043b\u044f",
    "\u043e\u0442\u043a\u0430\u0437\u0430\u043d\u043e \u0432 \u043f\u0440\u043e\u0434\u043e\u043b\u0436\u0435\u043d\u0438\u0438",
)


def text_looks_like_refusal(*parts: Any) -> bool:
    blob = " ".join(str(p or "") for p in parts).lower().replace("\u00a0", " ")
    return any(m in blob for m in REFUSAL_MARKERS)


def vacancy_looks_refused(v: Any) -> bool:
    hh = getattr(v, "hh_status", "") or ""
    if hh in ("discard", "deleted", "archived"):
        return True
    return text_looks_like_refusal(
        getattr(v, "description", ""),
        getattr(v, "hh_tag", ""),
        getattr(v, "title", ""),
    )
