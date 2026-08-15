# -*- coding: utf-8 -*-
"""HH vacancy search via Chrome CDP (no Selenium)."""
from __future__ import annotations

import re
import time
from typing import Dict, List, Optional

from .cdp import CdpError, CdpSession, open_and_eval, open_session
from .chrome_ctl import open_url_fast
from .chrome_lock import chrome_exclusive
from .cover_letter import make_cover_letter
from .queue_store import QueueStore, Vacancy, norm_url
from .scorer import score_vacancy
from .config import EXCLUDE_FILE, ROUNDS_GLOB, load_config, load_json


JS_CARDS = r"""
(() => {
  const out = [];
  const seen = new Set();
  function push(title, url, company, salary, snippet) {
    if (!url || seen.has(url)) return;
    seen.add(url);
    out.push({title: title||'', url, company: company||'', salary: salary||'', snippet: snippet||''});
  }
  document.querySelectorAll('a[data-qa="serp-item__title"], a[data-qa="vacancy-serp__vacancy-title"]').forEach(a => {
    const root = a.closest('[data-qa="vacancy-serp__vacancy"], .serp-item, article, div') || a.parentElement;
    const companyEl = root && root.querySelector('[data-qa="vacancy-serp__vacancy-employer"], [data-qa="vacancy-company-name"], a[data-qa="vacancy-serp__vacancy-employer"]');
    const salEl = root && root.querySelector('[data-qa="vacancy-serp__vacancy-compensation"], [data-qa="vacancy-salary"]');
    const snip = root ? (root.innerText||'').slice(0, 800) : '';
    push((a.innerText||'').trim(), a.href, companyEl ? (companyEl.innerText||'').trim() : '', salEl ? (salEl.innerText||'').trim() : '', snip);
  });
  if (out.length === 0) {
    document.querySelectorAll('a[href*="/vacancy/"]').forEach(a => {
      if (!/\/vacancy\/\d+/.test(a.href)) return;
      push((a.innerText||'').trim() || 'Vacancy', a.href, '', '', '');
    });
  }
  const needLogin = /account\/login/i.test(location.href);
  return { cards: out, href: location.href, needLogin, body: (document.body.innerText||'').slice(0, 500) };
})()
"""

JS_VACANCY_FULL = r"""
(() => {
  const needLogin = /account\/login/i.test(location.href);
  const titleEl =
    document.querySelector('[data-qa="vacancy-title"]') ||
    document.querySelector('h1[data-qa="bloko-header-1"]') ||
    document.querySelector('h1');
  const desc =
    document.querySelector('[data-qa="vacancy-description"]') ||
    document.querySelector('.vacancy-description') ||
    document.querySelector('[data-qa="vacancy-page"]');
  const bodyText = (document.body && document.body.innerText) || '';
  const descText = desc ? (desc.innerText || '') : '';
  // Полный текст страницы важнее узкого description: требования часто ниже/сбоку.
  const full = (bodyText.length >= descText.length ? bodyText : (descText + '\n' + bodyText));
  const salEl =
    document.querySelector('[data-qa="vacancy-salary"]') ||
    document.querySelector('[data-qa="vacancy-salary-compensation"]');
  let schedule = '';
  const m = bodyText.match(/Формат работы:\s*([^\n]+)/i);
  if (m) schedule = m[1].trim();
  let experience = '';
  const me = bodyText.match(/Опыт работы:\s*([^\n]+)/i);
  if (me) experience = me[1].trim();
  return {
    needLogin,
    title: titleEl ? (titleEl.innerText || '').trim() : (document.title || ''),
    salary: salEl ? (salEl.innerText || '').trim() : '',
    schedule,
    experience,
    text: full.slice(0, 30000),
    len: full.length,
  };
})()
"""


def load_excludes() -> set:
    out = set()
    data = load_json(EXCLUDE_FILE, {})
    for u in data.get("exclude_links") or []:
        out.add(norm_url(u))
    try:
        for p in ROUNDS_GLOB.glob("*круг вакансий*.md"):
            text = p.read_text(encoding="utf-8", errors="ignore")
            for m in re.findall(r"https?://(?:www\.)?hh\.ru/vacancy/\d+", text):
                out.add(norm_url(m))
    except Exception:
        pass
    return out


def _fetch_vacancy_details(session: CdpSession, url: str, settle: float) -> Optional[dict]:
    try:
        session.navigate(url, settle=settle)
        data = session.evaluate(JS_VACANCY_FULL, timeout=15)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def search_once(store: QueueStore) -> Dict:
    cfg = load_config()
    threshold = int(cfg.get("score_threshold") or 70)
    url = cfg.get("hh_search_url")
    excludes = load_excludes()
    deep = bool(cfg.get("deep_score", True))
    settle = float(cfg.get("vacancy_settle_sec") or 1.1)
    max_deep = int(cfg.get("deep_score_max") or 50)
    added = []
    skipped = 0
    deep_opened = 0
    t0 = time.time()

    # Deep scan держит Chrome дольше: SERP + N страниц вакансий.
    lock_timeout = 360.0 if deep else 100.0

    try:
        with chrome_exclusive(timeout=lock_timeout):
            session = open_session(url)
            try:
                session.navigate(url, settle=2.2)
                data = session.evaluate(JS_CARDS, timeout=15) or {}
                if data.get("needLogin"):
                    return {
                        "ok": False,
                        "error": "Нужен вход в HH. Нажмите «Войти в HH / Открыть Chrome» и залогиньтесь.",
                        "added": [],
                        "checked": 0,
                    }

                cards = data.get("cards") or []
                candidates: List[dict] = []
                for c in cards:
                    link = norm_url(c.get("url") or "")
                    if not link or link in excludes or store.known(link):
                        skipped += 1
                        continue
                    candidates.append(c)

                if deep:
                    candidates = candidates[: max(0, max_deep)]

                for c in candidates:
                    link = norm_url(c.get("url") or "")
                    title = (c.get("title") or "").strip() or "Без названия"
                    company = (c.get("company") or "").strip()
                    salary = (c.get("salary") or "").strip()
                    schedule = "удалённо"
                    experience = ""
                    snippet = c.get("snippet") or ""

                    if deep:
                        details = _fetch_vacancy_details(session, link, settle=settle)
                        deep_opened += 1
                        if details and details.get("needLogin"):
                            return {
                                "ok": False,
                                "error": "Нужен вход в HH (сессия слетела на странице вакансии).",
                                "added": added,
                                "checked": skipped + deep_opened,
                                "deep_opened": deep_opened,
                                "elapsed_sec": round(time.time() - t0, 1),
                            }
                        if details and (details.get("text") or "").strip():
                            snippet = str(details.get("text") or "")
                            if details.get("title"):
                                title = str(details["title"]).strip() or title
                            if details.get("salary"):
                                salary = str(details["salary"]).strip() or salary
                            if details.get("schedule"):
                                schedule = str(details["schedule"]).strip() or schedule
                            if details.get("experience"):
                                experience = str(details["experience"]).strip()

                    sc, reasons, ok = score_vacancy(
                        title,
                        snippet,
                        salary_text=salary,
                        schedule=schedule,
                        experience=experience,
                        salary_floor=int(cfg.get("salary_floor") or 120000),
                    )
                    if not ok or sc < threshold:
                        skipped += 1
                        continue

                    # Быстро: уникальное локальное письмо под текст.
                    # Cursor догоняет в фоне (см. upgrade_cover_letters), иначе поиск встанет на минуты.
                    letter, letter_src = make_cover_letter(
                        title,
                        company=company,
                        description=snippet,
                        salary=salary,
                        reasons=reasons,
                        force_local=True,
                    )
                    v = Vacancy(
                        id=link,
                        title=title,
                        company=company,
                        url=link,
                        score=sc,
                        reasons=reasons + (["deep:full-text"] if deep else ["serp-snippet"]),
                        salary=salary,
                        cover_letter=letter,
                        letter_source=letter_src,
                        description=(snippet or "")[:8000],
                        status="new",
                    )
                    if store.add(v):
                        added.append(v)
                    else:
                        skipped += 1
            finally:
                session.close()
    except TimeoutError as e:
        return {"ok": False, "error": str(e), "added": [], "checked": 0}
    except CdpError as e:
        return {"ok": False, "error": str(e), "added": [], "checked": 0}
    except Exception as e:
        return {"ok": False, "error": str(e), "added": [], "checked": 0}

    elapsed = round(time.time() - t0, 1)
    return {
        "ok": True,
        "added": added,
        "checked": skipped + len(added),
        "skipped": skipped,
        "deep_opened": deep_opened,
        "elapsed_sec": elapsed,
        "error": "",
        "href": url or "",
        "letter_upgrade_urls": [v.url for v in added],
    }


def upgrade_cover_letters(store: QueueStore, only_urls: Optional[set] = None) -> int:
    """Пересобрать письма через Cursor (или локально для stale-шаблонов)."""
    from .cover_letter import _api_key, is_stale_template

    cfg = load_config()
    want_cursor = bool(cfg.get("cover_letter_via_cursor", True))
    has_key = bool(_api_key(cfg))
    upgraded = 0
    for v in list(store.items):
        if only_urls is not None and v.url not in only_urls:
            continue
        stale = is_stale_template(v.cover_letter or "")
        empty = not (v.cover_letter or "").strip()
        need_cursor = want_cursor and has_key and v.letter_source != "cursor"
        if not (empty or stale or need_cursor):
            continue
        letter, src = make_cover_letter(
            v.title,
            company=v.company,
            description=v.description or "",
            salary=v.salary,
            reasons=v.reasons,
            force_local=not (want_cursor and has_key),
        )
        if letter and (letter != v.cover_letter or src != v.letter_source):
            v.cover_letter = letter
            v.letter_source = src
            upgraded += 1
            store.save()
    return upgraded


def open_vacancy_and_prepare(v: Vacancy) -> Dict:
    """Открыть вкладку как можно быстрее. Только буфер — без клика «Откликнуться»."""
    from .clipboard_util import set_clipboard

    # 1) Вкладка первой — письмо/буфер не блокируют.
    opened_fast = False
    try:
        opened_fast = bool(open_url_fast(v.url))
    except Exception:
        opened_fast = False

    if not opened_fast:
        # Fallback: navigate only (no form click / paste).
        try:
            from .cdp import open_and_eval

            open_and_eval(v.url, "(() => ({ok:true,href:location.href}))()", settle=0.4)
            opened_fast = True
            fast_mode = False
        except Exception as e:
            clip_ok = set_clipboard(v.cover_letter or "")
            return {
                "ok": False,
                "url": v.url,
                "title": v.title,
                "clicked": False,
                "pasted": False,
                "clipboard": clip_ok,
                "fast": False,
                "message": f"Не удалось открыть. Письмо в буфере: {clip_ok}. {e}",
            }
    else:
        fast_mode = True

    # 2) Буфер после открытия (если письмо уже есть).
    clip_ok = False
    if (v.cover_letter or "").strip():
        clip_ok = set_clipboard(v.cover_letter or "")

    who = f"«{v.title}» — " if v.title else ""
    if clip_ok:
        msg = f"{who}вкладка открыта, письмо в буфере (сам нажми «Откликнуться» → Ctrl+V)."
    elif (v.cover_letter or "").strip():
        msg = f"{who}вкладка открыта. Скопируйте письмо из Radar."
    else:
        msg = f"{who}вкладка открыта. Письмо ещё генерируется — будет двойной писк."

    return {
        "ok": True,
        "url": v.url,
        "title": v.title,
        "clicked": False,
        "pasted": False,
        "clipboard": clip_ok,
        "fast": fast_mode,
        "letter_pending": not bool((v.cover_letter or "").strip()),
        "message": msg,
    }


def _try_paste_cover_letter(url: str, letter: str, navigate: bool = False) -> None:
    """Устарело: автоклик «Откликнуться» отключён по запросу пользователя."""
    return
