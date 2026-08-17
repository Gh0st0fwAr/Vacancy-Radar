# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Iterable, List, Optional

from .config import QUEUE_PATH, SEEN_PATH, load_json, save_json
from .refusal import vacancy_looks_refused

# Не ходим по ним хоткеем.
HOTKEY_SKIP = frozenset({"banned", "skipped", "applied"})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm_url(url: str) -> str:
    if not url:
        return ""
    u = url.split("?")[0].rstrip("/")
    m = re.search(r"/vacancy/(\d+)", u)
    if m:
        return f"https://hh.ru/vacancy/{m.group(1)}"
    return u


def _found_at_key(v: "Vacancy") -> str:
    return getattr(v, "found_at", "") or ""


def is_hotkey_white(v: "Vacancy") -> bool:
    """
    Белая = ещё не откликался (локально и на HH).
    Серые отклики / синие ответы работодателя / отказы — не берём хоткеем.
    """
    if v.status in HOTKEY_SKIP:
        return False
    if vacancy_looks_refused(v):
        return False
    hh = getattr(v, "hh_status", "") or ""
    if hh in {"awaiting", "invitation", "interview", "hired", "chat", "discard", "deleted", "archived"}:
        return False
    return v.status in ("new", "visited") or not hh


@dataclass
class Vacancy:
    id: str
    title: str
    company: str
    url: str
    score: int
    reasons: List[str] = field(default_factory=list)
    salary: str = ""
    published: str = ""
    found_at: str = field(default_factory=utc_now)
    status: str = "new"  # new | visited | applied | skipped | banned
    cover_letter: str = ""
    letter_source: str = ""  # cursor | local
    description: str = ""
    remote: bool = True
    # Статус из «Отклики и приглашения» HH (CDP sync).
    hh_status: str = ""  # invitation | interview | hired | chat | awaiting | discard | …
    hh_tag: str = ""  # текст тега на HH, напр. «Не просмотрен»

    def short_line(self) -> str:
        return f"{self.score}% · {self.title} · {self.company}"


def pick_next_vacancy(
    items: List[Vacancy],
    active_url: str = "",
) -> Optional[Vacancy]:
    """
    Хоткей: только белые вакансии, от самой свежей к более старым (found_at desc), с wrap.
    """
    whites = [v for v in items if is_hotkey_white(v)]
    if not whites:
        return None
    whites.sort(key=_found_at_key, reverse=True)

    active = norm_url(active_url) if active_url else ""
    if not active:
        return whites[0]

    idx = next((i for i, v in enumerate(whites) if norm_url(v.url) == active), -1)
    if idx < 0:
        return whites[0]
    if len(whites) == 1:
        return whites[0]
    return whites[(idx + 1) % len(whites)]


class QueueStore:
    def __init__(self, *, autoload: bool = True) -> None:
        self.items: List[Vacancy] = []
        self.seen: set[str] = set()
        self.pointer: int = 0
        self.active_url: str = ""
        if autoload:
            self.load()

    def load(self) -> None:
        raw = load_json(QUEUE_PATH, {"items": [], "pointer": 0, "active_url": ""})
        self.pointer = int(raw.get("pointer") or 0)
        self.active_url = str(raw.get("active_url") or "")
        self.items = []
        for it in raw.get("items") or []:
            try:
                self.items.append(Vacancy(**it))
            except TypeError:
                keys = Vacancy.__dataclass_fields__.keys()
                self.items.append(Vacancy(**{k: it[k] for k in keys if k in it}))
        self.seen = set(load_json(SEEN_PATH, []))
        if self.active_url:
            self.active_url = norm_url(self.active_url)
        self.purge_refused(persist=True)

    def purge_refused(self, *, persist: bool = True) -> int:
        """Убрать отказы из очереди; URL остаётся в seen (не вернётся из поиска)."""
        keep = []
        removed = 0
        for v in self.items:
            if vacancy_looks_refused(v):
                removed += 1
                nid = norm_url(v.url)
                if nid:
                    self.seen.add(nid)
                if norm_url(self.active_url) == nid:
                    self.active_url = ""
                continue
            keep.append(v)
        if removed:
            self.items = keep
            if persist:
                self.save()
        return removed

    def save(self) -> None:
        save_json(
            QUEUE_PATH,
            {
                "pointer": self.pointer,
                "active_url": self.active_url,
                "items": [asdict(v) for v in self.items],
            },
        )
        save_json(SEEN_PATH, sorted(self.seen))

    def set_active(self, url: str, *, persist: bool = True) -> None:
        """Запомнить вакансию, открытую хоткеем / из UI (указатель)."""
        nid = norm_url(url)
        self.active_url = nid
        if nid:
            for i, v in enumerate(self.items):
                if norm_url(v.url) == nid:
                    self.pointer = i
                    break
        if persist:
            self.save()

    def in_queue(self, url: str) -> bool:
        nid = norm_url(url)
        return bool(nid) and any(norm_url(v.url) == nid for v in self.items)

    def forget_seen(self, urls: Iterable[str], *, persist: bool = True) -> int:
        """Remove URLs from seen so search can rescore them."""
        removed = 0
        for u in urls:
            nid = norm_url(u)
            if nid and nid in self.seen:
                self.seen.discard(nid)
                removed += 1
        if removed and persist:
            self.save()
        return removed

    def remember(self, url: str, *, persist: bool = True) -> None:
        """Mark URL as seen without adding to queue (skip future search/score)."""
        nid = norm_url(url)
        if not nid:
            return
        self.seen.add(nid)
        if persist:
            self.save()

    def known(self, url: str) -> bool:
        return norm_url(url) in self.seen or any(
            norm_url(v.url) == norm_url(url) for v in self.items
        )

    def add(self, v: Vacancy) -> bool:
        nid = norm_url(v.url)
        if not nid or self.known(nid):
            return False
        v.url = nid
        v.id = v.id or nid
        self.items.insert(0, v)  # newest first
        self.seen.add(nid)
        self.save()
        return True

    _STATUS_RANK = {"new": 0, "visited": 1, "skipped": 2, "applied": 3}

    def mark(self, url: str, status: str) -> None:
        nid = norm_url(url)
        if status == "banned":
            self.items = [v for v in self.items if norm_url(v.url) != nid]
            if nid:
                self.seen.add(nid)
            if norm_url(self.active_url) == nid:
                self.active_url = ""
            self.save()
            return
        new_rank = self._STATUS_RANK.get(status, 0)
        for v in self.items:
            if norm_url(v.url) == nid:
                old_rank = self._STATUS_RANK.get(v.status, 0)
                if new_rank < old_rank:
                    return
                v.status = status
                break
        self.save()

    def next_unvisited(self) -> Optional[Vacancy]:
        for v in self.items:
            if v.status == "new":
                return v
        return None

    def open_next(self) -> Optional[Vacancy]:
        """Следующая вакансия после указателя (см. pick_next_vacancy)."""
        self.purge_refused(persist=True)
        return pick_next_vacancy(self.items, self.active_url)
