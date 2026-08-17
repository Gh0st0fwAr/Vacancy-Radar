# -*- coding: utf-8 -*-
"""Sync HH applicant negotiations into the Radar queue via CDP."""
from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional, Tuple

from .config import NEGOTIATIONS_PATH, save_json
from .queue_store import HOTKEY_SKIP, QueueStore, Vacancy, norm_url, utc_now

FILTER_TABS: Tuple[Tuple[str, str], ...] = (
    ("invitation", "invitation"),
    ("interview", "interview"),
    ("hired", "hired"),
    ("awaiting", "awaiting"),
    ("discard", "discard"),
    ("deleted", "deleted"),
    ("archived", "archived"),
)

TERMINAL_HH = frozenset({"discard", "deleted", "archived"})
HIGHLIGHT_HH = frozenset({"invitation", "interview", "hired", "chat"})
APPLIED_HH = frozenset({"invitation", "interview", "hired", "awaiting", "chat"})
RANK = {
    "discard": 50, "deleted": 50, "archived": 50,
    "hired": 40, "interview": 35, "invitation": 30, "chat": 28, "awaiting": 10,
}

JS_SCRAPE_ITEMS = r"""
(() => {
  const items = [];
  const nodes = [...document.querySelectorAll('[data-qa="negotiations-item"]')];
  for (const el of nodes) {
    const vacEl = el.querySelector('[data-qa="negotiations-item-vacancy"]');
    const coEl = el.querySelector('[data-qa="negotiations-item-company"]');
    const tagEl = el.querySelector('[data-qa*="negotiations-tag"]');
    const vacLink = el.querySelector('a[href*="/vacancy/"]');
    let href = vacLink ? (vacLink.href || '') : '';
    if (!href && vacEl) {
      const a = vacEl.closest('a') || vacEl.querySelector('a') || (vacEl.tagName === 'A' ? vacEl : null);
      href = (a && a.href) || '';
    }
    const tagQa = tagEl ? (tagEl.getAttribute('data-qa') || '') : '';
    const full = (el.innerText || '').replace(/\u00a0/g, ' ');
    const employerReply = /\u043e\u0442\u0432\u0435\u0442\u0438\u043b|\u043d\u043e\u0432\u044b\u0439 \u0447\u0430\u0442|\u0432\u0430\u043c \u043d\u0430\u043f\u0438\u0441\u0430|\u043d\u043e\u0432\u043e\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d|\u0440\u0430\u0431\u043e\u0442\u043e\u0434\u0430\u0442\u0435\u043b\u044c.{0,40}(\u043d\u0430\u043f\u0438\u0441\u0430\u043b|\u043e\u0442\u0432\u0435\u0442\u0438\u043b)|\u0435\u0441\u0442\u044c \u0441\u043e\u043e\u0431\u0449\u0435\u043d/i.test(full)
      || /negotiations-item-(response|reply|message|invitation|interview|hired)/i.test(tagQa);
    items.push({
      title: vacEl ? (vacEl.innerText || '').replace(/\u00a0/g, ' ').trim() : '',
      company: coEl ? (coEl.innerText || '').replace(/\u00a0/g, ' ').trim() : '',
      tag: tagEl ? (tagEl.innerText || '').replace(/\u00a0/g, ' ').trim() : '',
      tag_qa: tagQa,
      href,
      employer_reply: !!employerReply,
    });
  }
  const body = (document.body && document.body.innerText) || '';
  return {
    needLogin: /\u0432\u043e\u0439\u0434\u0438\u0442\u0435|\u0430\u0432\u0442\u043e\u0440\u0438\u0437\u0443\u0439/i.test(body)
      && items.length === 0,
    href: location.href,
    count: items.length,
    items,
  };
})()
"""

JS_CLICK_TAB = r"""
(qa) => {
  const el = document.querySelector('[data-qa="' + qa + '"]')
    || document.querySelector('[data-qa="wrapper-' + qa + '"]');
  if (!el) return { ok: false, reason: 'missing' };
  el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true, view: window}));
  el.click();
  return { ok: true, qa };
}
"""

JS_SCROLL = r"""
(() => {
  const box = document.querySelector('[data-qa="negotiations-list"]') || document.scrollingElement;
  if (box) { box.scrollTop = box.scrollHeight; }
  window.scrollTo(0, document.body.scrollHeight);
  const btn = [...document.querySelectorAll('button,a')].find(el =>
    /\u043f\u043e\u043a\u0430\u0437|\u0435\u0449\u0451|\u0435\u0449\u0435/i.test((el.innerText || '').trim())
  );
  if (btn) { btn.click(); return { scrolled: true, clickedMore: true }; }
  return { scrolled: true, clickedMore: false, count: document.querySelectorAll('[data-qa="negotiations-item"]').length };
})()
"""


def _vacancy_id_from_href(href: str) -> str:
    if not href:
        return ""
    m = re.search(r"/vacancy/(\d+)", href)
    return m.group(1) if m else ""


def status_from_tags(
    tag_qa: str = "",
    tag_text: str = "",
    filter_key: str = "",
    *,
    employer_reply: bool = False,
) -> str:
    qa = (tag_qa or "").lower()
    text = (tag_text or "").lower().replace("\u00a0", " ")
    filt = (filter_key or "").lower()
    if "discard" in qa or "\u043e\u0442\u043a\u0430\u0437" in text:
        return "discard"
    if "deleted" in qa or "\u0443\u0434\u0430\u043b" in text:
        return "deleted"
    if "archived" in qa or "\u0430\u0440\u0445\u0438\u0432" in text:
        return "archived"
    if "hired" in qa or "\u0432\u044b\u0445\u043e\u0434 \u043d\u0430" in text:
        return "hired"
    if "interview" in qa or "\u0441\u043e\u0431\u0435\u0441\u0435\u0434" in text:
        return "interview"
    if "invitation" in qa or "\u043f\u0440\u0438\u0433\u043b\u0430\u0448" in text:
        return "invitation"
    if employer_reply or "response" in qa or "reply" in qa or "message" in qa:
        return "chat"
    if (
        "not-viewed" in qa
        or "viewed" in qa
        or "\u043d\u0435 \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440" in text
        or "\u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0435\u043d" in text
    ):
        return "awaiting"
    if filt in RANK:
        return filt
    if "\u043e\u0436\u0438\u0434" in text:
        return "awaiting"
    return filt or "awaiting"


def soft_company(name: str) -> str:
    s = (name or "").lower().replace("\u00a0", " ").strip()
    s = re.sub(r"\s+", " ", s)
    for pref in ("\u043e\u043e\u043e ", "\u0438\u043f ", "\u0430\u043e ", "\u043f\u0430\u043e ", "\u0437\u0430\u043e ", "\u043e\u0430\u043e ", "llc ", "ltd ", "inc "):
        if s.startswith(pref):
            s = s[len(pref):]
    return s.strip(" .,\"'")


def title_company_key(title: str, company: str) -> str:
    return f"{(title or '').strip().lower()}|{soft_company(company)}"


def normalize_item(raw: Dict[str, Any], filter_key: str = "") -> Optional[Dict[str, Any]]:
    href = str(raw.get("href") or raw.get("href_raw") or "")
    vid = _vacancy_id_from_href(href)
    title = str(raw.get("title") or "").strip()
    company = str(raw.get("company") or "").strip()
    if not vid and not title:
        return None
    url = f"https://hh.ru/vacancy/{vid}" if vid else ""
    tag_qa = str(raw.get("tag_qa") or "")
    tag = str(raw.get("tag") or "").strip()
    employer_reply = bool(raw.get("employer_reply"))
    hh = status_from_tags(tag_qa, tag, filter_key, employer_reply=employer_reply)
    return {
        "id": vid or url or f"{title}|{company}",
        "url": url,
        "title": title,
        "company": company,
        "tag": tag,
        "tag_qa": tag_qa,
        "hh_status": hh,
        "href_raw": href,
        "employer_reply": employer_reply,
    }


def _merge_item(by_key: Dict[str, Dict[str, Any]], norm: Dict[str, Any]) -> None:
    key = norm["url"] or title_company_key(norm["title"], norm["company"])
    prev = by_key.get(key)
    if prev is None:
        by_key[key] = norm
        return
    if RANK.get(norm["hh_status"], 0) >= RANK.get(prev["hh_status"], 0):
        by_key[key] = norm


def _wait_for_items(session, timeout: float = 8.0) -> int:
    deadline = time.time() + timeout
    last = 0
    while time.time() < deadline:
        try:
            n = session.evaluate(
                "document.querySelectorAll('[data-qa=\"negotiations-item\"]').length",
                timeout=5,
            )
            last = int(n or 0)
            if last > 0:
                return last
        except Exception:
            pass
        time.sleep(0.4)
    return last


def _scrape_current(session, filter_key: str, by_key: Dict[str, Dict[str, Any]]) -> bool:
    _wait_for_items(session, timeout=8.0)
    for _ in range(4):
        try:
            session.evaluate(JS_SCROLL, timeout=5)
        except Exception:
            pass
        time.sleep(0.45)
    try:
        raw = session.evaluate(JS_SCRAPE_ITEMS, timeout=12) or {}
    except Exception:
        time.sleep(1.2)
        try:
            raw = session.evaluate(JS_SCRAPE_ITEMS, timeout=12) or {}
        except Exception:
            return True
    if raw.get("needLogin"):
        return False
    for it in raw.get("items") or []:
        norm = normalize_item(it, filter_key)
        if norm:
            _merge_item(by_key, norm)
    return True


def scrape_negotiations(session) -> List[Dict[str, Any]]:
    by_key: Dict[str, Dict[str, Any]] = {}
    session.navigate("https://hh.ru/applicant/negotiations", settle=2.6)
    if not _scrape_current(session, "awaiting", by_key):
        items: List[Dict[str, Any]] = []
        save_json(NEGOTIATIONS_PATH, {"updated_at": utc_now(), "count": 0, "items": items})
        return items
    for tab_qa_suffix, filter_key in FILTER_TABS:
        qa = f"tab_filter_{tab_qa_suffix}"
        try:
            clicked = session.evaluate(f"({JS_CLICK_TAB})({qa!r})", timeout=8) or {}
        except Exception:
            clicked = {}
        time.sleep(1.6 if clicked.get("ok") else 0.3)
        if not _scrape_current(session, filter_key, by_key):
            break
    items = list(by_key.values())
    save_json(NEGOTIATIONS_PATH, {"updated_at": utc_now(), "count": len(items), "items": items})
    return items


def apply_negotiations(store: QueueStore, items: List[Dict[str, Any]]) -> Dict[str, int]:
    items = items or []
    added = updated = removed = promoted = 0
    by_url: Dict[str, Dict[str, Any]] = {}
    by_title_co: Dict[str, Dict[str, Any]] = {}
    for it in items:
        u = norm_url(it.get("url") or "")
        if u:
            by_url[u] = it
        tkey = title_company_key(it.get("title") or "", it.get("company") or "")
        if tkey != "|":
            by_title_co[tkey] = it

    def match(v: Vacancy) -> Optional[Dict[str, Any]]:
        u = norm_url(v.url)
        if u and u in by_url:
            return by_url[u]
        return by_title_co.get(title_company_key(v.title, v.company))

    keep: List[Vacancy] = []
    for v in store.items:
        info = match(v)
        if info and info.get("hh_status") in TERMINAL_HH:
            removed += 1
            if norm_url(store.active_url) == norm_url(v.url):
                store.active_url = ""
            continue
        if info:
            hh = str(info.get("hh_status") or "")
            changed = False
            if hh and getattr(v, "hh_status", "") != hh:
                v.hh_status = hh
                changed = True
            tag = str(info.get("tag") or "")
            if tag and getattr(v, "hh_tag", "") != tag:
                v.hh_tag = tag
                changed = True
            if hh in APPLIED_HH and v.status not in ("banned", "skipped") and v.status != "applied":
                if v.status == "visited":
                    promoted += 1
                v.status = "applied"
                changed = True
            if changed:
                updated += 1
        keep.append(v)
    store.items = keep

    existing_urls = {norm_url(v.url) for v in store.items}
    existing_tc = {title_company_key(v.title, v.company) for v in store.items}

    for it in items:
        hh = str(it.get("hh_status") or "")
        if hh in TERMINAL_HH:
            continue
        url = norm_url(it.get("url") or "")
        tkey = title_company_key(it.get("title") or "", it.get("company") or "")
        if url and url in existing_urls:
            continue
        if tkey in existing_tc:
            continue
        if not url and tkey == "|":
            continue
        v = Vacancy(
            id=str(it.get("id") or url or tkey),
            title=str(it.get("title") or "\u0411\u0435\u0437 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u044f"),
            company=str(it.get("company") or ""),
            url=url or "https://hh.ru/applicant/negotiations",
            score=0,
            reasons=["\u0421\u0438\u043d\u0445\u0440\u043e\u043d\u0438\u0437\u0430\u0446\u0438\u044f \u0438\u0437 \u043e\u0442\u043a\u043b\u0438\u043a\u043e\u0432 HH"],
            status="applied" if hh in APPLIED_HH else "visited",
            hh_status=hh,
            hh_tag=str(it.get("tag") or ""),
            remote=True,
        )
        store.items.append(v)
        if url:
            store.seen.add(url)
            existing_urls.add(url)
        existing_tc.add(tkey)
        added += 1

    def sort_key(v: Vacancy):
        hh = getattr(v, "hh_status", "") or ""
        prio = {"hired": 5, "interview": 4, "invitation": 3, "chat": 3}.get(hh, 0)
        if prio == 0 and v.status == "new":
            prio = 2
        elif prio == 0 and hh == "awaiting":
            prio = 1
        return (-prio, -(v.score or 0), v.found_at or "")

    store.items.sort(key=sort_key)
    store.purge_refused(persist=False)
    store.save()
    return {"added": added, "updated": updated, "removed": removed, "promoted": promoted, "total": len(items)}


def badge_for(v: Vacancy) -> str:
    hh = getattr(v, "hh_status", "") or ""
    if hh == "invitation":
        return "[\u041f\u0420\u0418\u0413\u041b] "
    if hh == "interview":
        return "[\u0421\u041e\u0411\u0415\u0421] "
    if hh == "hired":
        return "[\u041e\u0424\u0424\u0415\u0420] "
    if hh == "chat":
        return "[\u0427\u0410\u0422] "
    if hh == "awaiting" or v.status == "applied":
        return "[\u041e\u0422\u041a\u041b] "
    return ""


assert "applied" in HOTKEY_SKIP
