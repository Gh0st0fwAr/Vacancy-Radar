# -*- coding: utf-8 -*-
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from .config import QUEUE_PATH, SEEN_PATH, load_json, save_json

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

    def short_line(self) -> str:
        return f"{self.score}% · {self.title} · {self.company}"


def pick_next_vacancy(
    items: List[Vacancy],
    active_url: str = "",
) -> Optional[Vacancy]:
    """
    Следующая вакансия для хоткея.
    1) Если есть status=new — берём первую new ПОСЛЕ active_url (с wrap).
    2) Иначе — следующая после active среди обходимых (visited и т.п.), с циклом.
    Не возвращает ту же, что active, если в очереди есть другая доступная.
    """
    pool = [v for v in items if v.status not in HOTKEY_SKIP]
    if not pool:
        return None

    active = norm_url(active_url) if active_url else ""
    news = [v for v in pool if v.status == "new"]

    if news:
        if not active:
            return news[0]
        after = False
        for v in pool:
            if norm_url(v.url) == active:
                after = True
                continue
            if after and v.status == "new":
                return v
        # wrap: new до/включая начало списка (но не сама active, если она уже не new)
        for v in news:
            if norm_url(v.url) != active:
                return v
        return news[0]

    # Нет new — шаг по пулу после active
    if not active:
        return pool[0]
    idx = next((i for i, v in enumerate(pool) if norm_url(v.url) == active), -1)
    if idx < 0:
        return pool[0]
    if len(pool) == 1:
        return pool[0]
    return pool[(idx + 1) % len(pool)]


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

    def mark(self, url: str, status: str) -> None:
        nid = norm_url(url)
        if status == "banned":
            # Удалить из очереди навсегда; seen не даст вернуться из поиска.
            self.items = [v for v in self.items if norm_url(v.url) != nid]
            if nid:
                self.seen.add(nid)
            if norm_url(self.active_url) == nid:
                self.active_url = ""
            self.save()
            return
        for v in self.items:
            if norm_url(v.url) == nid:
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
        return pick_next_vacancy(self.items, self.active_url)
