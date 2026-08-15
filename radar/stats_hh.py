# -*- coding: utf-8 -*-
"""Pull HH applicant stats via Chrome CDP (Magritte UI)."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Optional

from .cdp import CdpError, open_session
from .chrome_lock import chrome_exclusive
from .config import STATS_PATH, load_json, save_json

# Frontend resume to track (not the welder one)
RESUME_HINTS = (
    "frontend developer",
    "vue 3",
    "typescript",
    "18497a9cff07872e2a0039ed1f4b4b58594666",
)

JS_NEGOTIATIONS = r"""
(() => {
  const text = (document.body && document.body.innerText) ? document.body.innerText : '';
  const needLogin = /войдите|авторизуй/i.test(text) && !/отклик|приглашен|ожидание/i.test(text);

  // Magritte filter chips: "Все\n26", "Ожидание\n18", ...
  const tabs = {};
  const nodes = [...document.querySelectorAll('a,button,div,span')];
  for (const el of nodes) {
    const t = (el.innerText || '').replace(/\u00a0/g, ' ').trim();
    if (!t || t.length > 40) continue;
    const m = t.match(/^(Все|Приглашени[ея]|Собеседование|Выход на работу|Ожидание|Отказ|Отклон[её]нные|Удал[её]нные|Архив)\s*\n?\s*(\d+)\s*$/i);
    if (m) {
      const key = m[1].toLowerCase();
      tabs[key] = parseInt(m[2], 10);
      continue;
    }
    // split children style: label then number sibling already covered by innerText
  }

  // Also parse compact block text
  const block = nodes.map(e => (e.innerText||'').trim()).find(t => /^Все\n\d+/m.test(t) && /Ожидание/i.test(t));
  if (block) {
    for (const m of block.matchAll(/(Все|Приглашени[ея]|Собеседование|Ожидание|Отказ|Удал[её]нные)\s*\n\s*(\d+)/gi)) {
      tabs[m[1].toLowerCase()] = parseInt(m[2], 10);
    }
  }

  let responded = null;
  const rm = text.replace(/\u00a0/g,' ').match(/Вы\s+откликнулись\s+(\d+)/i);
  if (rm) responded = parseInt(rm[1], 10);

  return { needLogin, tabs, responded, href: location.href, sample: text.slice(0, 1500) };
})()
"""

JS_PROFILE = r"""
(() => {
  const want = ['frontend developer', 'vue 3', 'typescript'];
  const bodyText = document.body ? (document.body.innerText || '') : '';
  const needLogin = /войдите|авторизуй/i.test(bodyText) && !/мои резюме|просмотры/i.test(bodyText);

  function parseCard(text) {
    const t = (text || '').replace(/\u00a0/g, ' ');
    let views = null, inv = null;
    const vm = t.match(/Просмотры\s*[\n\r]+\s*([–—-]|\d+)/i);
    const im = t.match(/Приглашени[ея]\s*[\n\r]+\s*([–—-]|\d+)/i);
    if (vm) views = vm[1].match(/\d+/) ? parseInt(vm[1], 10) : null;
    if (im) inv = im[1].match(/\d+/) ? parseInt(im[1], 10) : null;
    return { views, invitations: inv };
  }

  const cards = [...document.querySelectorAll('[data-qa="resume"], [data-qa="compact-resume-list"] [data-qa="resume"], [data-qa^="resume-card-link"]')];
  let chosen = null;
  for (const c of cards) {
    const t = (c.innerText || '');
    const low = t.toLowerCase();
    if (want.some(w => low.includes(w))) {
      const titleEl = c.querySelector('[data-qa="resume-title"]');
      chosen = {
        title: titleEl ? (titleEl.innerText || '').trim() : '',
        ...parseCard(t),
        source: 'resume-card'
      };
      break;
    }
  }
  if (!chosen) {
    const viewsEls = [...document.querySelectorAll('[data-qa="count-new-views"]')];
    for (const el of viewsEls) {
      const parentText = el.parentElement ? el.parentElement.innerText : el.innerText;
      const p = parseCard(parentText);
      if (p.views != null || p.invitations != null) {
        chosen = { title: '', ...p, source: 'count-new-views' };
        break;
      }
    }
  }

  let responded = null;
  const rm = bodyText.replace(/\u00a0/g,' ').match(/Вы\s+откликнулись\s+(\d+)/i);
  if (rm) responded = parseInt(rm[1], 10);

  return { needLogin, resume: chosen, responded, href: location.href };
})()
"""


def _merge(prev: Dict, new: Dict) -> Dict:
    """Keep previous numeric values when new scrape returned null."""
    out = dict(prev or {})
    out.update({k: v for k, v in new.items() if k not in ("raw_notes",)})
    keep_keys = (
        "active_responses",
        "invitations",
        "unread_messages",
        "resume_views",
        "resume_shows",
        "total_responses",
        "interviews",
        "refusals",
    )
    for k in keep_keys:
        if new.get(k) is None and prev.get(k) is not None:
            out[k] = prev[k]
    # notes always from new
    out["raw_notes"] = new.get("raw_notes") or []
    out["updated_at"] = new.get("updated_at") or out.get("updated_at")
    out["ok"] = bool(new.get("ok"))
    out["error"] = new.get("error") or ""
    out["stale"] = False
    # if new ok but all core metrics null while prev had values — mark soft
    core = ("active_responses", "invitations", "resume_views", "total_responses")
    if new.get("ok") and all(new.get(k) is None for k in core) and any(prev.get(k) is not None for k in core):
        out["stale"] = True
        out["raw_notes"] = list(out.get("raw_notes") or []) + ["Часть полей не прочиталась — оставлены прошлые значения"]
    return out


def fetch_stats() -> Dict:
    prev = load_json(STATS_PATH, {})
    out: Dict[str, Any] = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "active_responses": None,
        "invitations": None,
        "unread_messages": None,
        "resume_views": None,
        "resume_shows": None,
        "total_responses": None,
        "interviews": None,
        "refusals": None,
        "raw_notes": [],
        "ok": False,
        "error": "",
        "stale": False,
    }
    session = None
    try:
        with chrome_exclusive(timeout=100):
            session = open_session("https://hh.ru/applicant/negotiations")

            # 1) Negotiations filters
            session.navigate("https://hh.ru/applicant/negotiations", settle=3.2)
            neg = session.evaluate(JS_NEGOTIATIONS, timeout=15) or {}
            if neg.get("needLogin"):
                out["error"] = "Нужен логин HH в Chrome Radar"
                merged = _merge(prev, out)
                save_json(STATS_PATH, merged)
                return merged

            tabs = {str(k).lower(): v for k, v in (neg.get("tabs") or {}).items()}
            # Magritte: Ожидание ≈ активные без финала; Все = всего в работе
            out["active_responses"] = _tab(tabs, "ожидание")
            out["total_responses"] = _tab(tabs, "все") or neg.get("responded")
            out["interviews"] = _tab(tabs, "собеседование")
            out["refusals"] = _tab(tabs, "отказ")
            # invitations from negotiations tab if present
            inv_tab = _tab(tabs, "приглашение") or _tab(tabs, "приглашения")
            if inv_tab is not None:
                out["invitations"] = inv_tab

            # 2) Profile / resumes — views + invites for Frontend CV
            # /applicant/resumes redirects to profile/me on Magritte
            session.navigate("https://hh.ru/applicant/profile/me", settle=3.2)
            prof = session.evaluate(JS_PROFILE, timeout=15) or {}
            if prof.get("needLogin"):
                out["error"] = "Нужен логин HH в Chrome Radar"
            resume = prof.get("resume") or {}
            if resume.get("views") is not None:
                out["resume_views"] = resume.get("views")
            if resume.get("invitations") is not None:
                out["invitations"] = resume.get("invitations")
            if out["total_responses"] is None and prof.get("responded") is not None:
                out["total_responses"] = prof.get("responded")

            # 3) Chat unread (optional)
            try:
                session.navigate("https://chatik.hh.ru/", settle=1.8)
                unread = session.evaluate(
                    """(() => {
                  const b = document.body ? document.body.innerText : '';
                  const m = b.match(/(\\d+)\\s*непрочит/i);
                  if (m) return parseInt(m[1], 10);
                  const badge = [...document.querySelectorAll('[class*=badge], [data-qa*=unread]')]
                    .map(e => parseInt((e.innerText||'').trim(), 10)).filter(n => !isNaN(n));
                  return badge.length ? badge[0] : 0;
                })()""",
                    timeout=10,
                )
                out["unread_messages"] = unread
            except Exception:
                out["unread_messages"] = None

            out["ok"] = True
            out["raw_notes"] = [
                f"negotiations tabs={tabs}",
                f"resume={resume}",
                f"href_neg={neg.get('href')}",
                f"href_prof={prof.get('href')}",
            ]
    except TimeoutError as e:
        out["error"] = str(e)
    except CdpError as e:
        out["error"] = str(e)
    except Exception as e:
        out["error"] = str(e)
    finally:
        if session is not None:
            try:
                session.close()
            except Exception:
                pass

    merged = _merge(prev, out)
    # If failed entirely, keep previous numbers but surface error
    if not out.get("ok") and prev:
        for k in (
            "active_responses",
            "invitations",
            "unread_messages",
            "resume_views",
            "resume_shows",
            "total_responses",
            "interviews",
            "refusals",
        ):
            if merged.get(k) is None:
                merged[k] = prev.get(k)
        merged["stale"] = True
        merged["raw_notes"] = list(merged.get("raw_notes") or []) + ["Ошибка обновления — показаны прошлые цифры"]
    save_json(STATS_PATH, merged)
    return merged


def _tab(tabs: dict, name: str) -> Optional[int]:
    name = name.lower()
    if name in tabs:
        return tabs[name]
    for k, v in tabs.items():
        if name in k:
            return v
    return None
