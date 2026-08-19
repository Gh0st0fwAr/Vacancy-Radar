# -*- coding: utf-8 -*-
"""HH vacancy search via Chrome CDP (no Selenium)."""
from __future__ import annotations

import re
import threading
import time
from typing import Callable, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .cdp import CdpError, CdpSession, open_and_eval, open_session
from .chrome_ctl import open_url_fast
from .chrome_lock import chrome_exclusive
from .cover_letter import make_cover_letter
from .queue_store import QueueStore, Vacancy, norm_url
from .refusal import text_looks_like_refusal
from .cursor_score import score_many_parallel
from .config import EXCLUDE_FILE, ROUNDS_GLOB, load_config, load_json
from .metrics_log import append_event


JS_CARDS = r"""
(() => {
  const out = [];
  const seen = new Set();
  function isVisited(root, a) {
    const nodes = [];
    let el = root || a;
    for (let i = 0; i < 6 && el; i++) {
      nodes.push(el);
      el = el.parentElement;
    }
    if (a) nodes.push(a);
    for (const n of nodes) {
      if (!n) continue;
      const cls = String(n.className || '');
      if (/visited/i.test(cls)) return true;
      try {
        if (n.matches && (
          n.matches('.vacancy-serp-item_visited') ||
          n.matches('[class*="serp-item_visited"]') ||
          n.matches('[class*="--visited"]') ||
          n.matches('[data-qa*="visited"]')
        )) return true;
      } catch (e) {}
      if (n.getAttribute) {
        const dv = n.getAttribute('data-visited') || n.getAttribute('data-qa-visited');
        if (dv === 'true' || dv === '1') return true;
      }
    }
    return false;
  }
  function push(title, url, company, salary, snippet, visited) {
    if (!url || seen.has(url)) return;
    seen.add(url);
    out.push({
      title: title||'',
      url,
      company: company||'',
      salary: salary||'',
      snippet: snippet||'',
      visited: !!visited,
    });
  }
  document.querySelectorAll('a[data-qa="serp-item__title"], a[data-qa="vacancy-serp__vacancy-title"]').forEach(a => {
    const root = a.closest('[data-qa="vacancy-serp__vacancy"], .serp-item, .vacancy-serp-item, article, div') || a.parentElement;
    const companyEl = root && root.querySelector('[data-qa="vacancy-serp__vacancy-employer"], [data-qa="vacancy-company-name"], a[data-qa="vacancy-serp__vacancy-employer"], [data-qa="vacancy-serp__vacancy-employer-text"]');
    const salEl = root && root.querySelector('[data-qa="vacancy-serp__vacancy-compensation"], [data-qa="vacancy-salary"]');
    const snip = root ? (root.innerText||'').slice(0, 800) : '';
    push((a.innerText||'').trim(), a.href, companyEl ? (companyEl.innerText||'').trim() : '', salEl ? (salEl.innerText||'').trim() : '', snip, isVisited(root, a));
  });
  if (out.length === 0) {
    document.querySelectorAll('a[href*="/vacancy/"]').forEach(a => {
      if (!/\/vacancy\/\d+/.test(a.href)) return;
      const root = a.closest('[data-qa="vacancy-serp__vacancy"], .serp-item, .vacancy-serp-item, article, div') || a.parentElement;
      push((a.innerText||'').trim() || 'Vacancy', a.href, '', '', '', isVisited(root, a));
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


def load_excludes(cfg: Optional[dict] = None) -> set:
    cfg = cfg or load_config()
    out = set()
    data = load_json(EXCLUDE_FILE, {})
    for u in data.get("exclude_links") or []:
        out.add(norm_url(u))
    if bool(cfg.get("exclude_manual_rounds", False)):
        try:
            for p in ROUNDS_GLOB.glob("*круг вакансий*.md"):
                text = p.read_text(encoding="utf-8", errors="ignore")
                for m in re.findall(r"https?://(?:www\.)?hh\.ru/vacancy/\d+", text):
                    out.add(norm_url(m))
        except Exception:
            pass
    return out


def _with_search_period(url: str, days: int) -> str:
    """Set/replace the search_period query param. HH uses integer days."""
    days = max(1, int(days))
    parsed = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k != "search_period"]
    q.append(("search_period", str(days)))
    return urlunparse(parsed._replace(query=urlencode(q)))


def _serp_page_url(base: str, page: int) -> str:
    parsed = urlparse(base)
    q = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if page <= 0:
        q.pop("page", None)
    else:
        q["page"] = str(page)
    return urlunparse(parsed._replace(query=urlencode(q)))


def _collect_serp_cards(
    session: CdpSession,
    base_url: str,
    max_pages: int,
    on_progress: Optional[Callable[[str], None]] = None,
) -> tuple[List[dict], dict]:
    all_cards: List[dict] = []
    seen_urls: set[str] = set()
    last_href = base_url
    pages_done = 0
    for page in range(max(1, max_pages)):
        page_url = _serp_page_url(base_url, page)
        if on_progress:
            on_progress(f"SERP {page + 1}/{max_pages}…")
        session.navigate(page_url, settle=2.2 if page == 0 else 1.7)
        data = session.evaluate(JS_CARDS, timeout=15) or {}
        if data.get("needLogin"):
            return all_cards, {"needLogin": True, "href": data.get("href") or page_url}
        last_href = str(data.get("href") or page_url)
        cards = data.get("cards") or []
        new_on_page = 0
        for c in cards:
            link = norm_url(c.get("url") or "")
            if not link or link in seen_urls:
                continue
            seen_urls.add(link)
            all_cards.append(c)
            new_on_page += 1
        if on_progress:
            on_progress(f"SERP {page + 1}: карточек {len(cards)}, новых {new_on_page}, всего {len(all_cards)}")
        if page > 0 and new_on_page == 0:
            break
        pages_done = page + 1
    return all_cards, {"needLogin": False, "href": last_href, "pages": pages_done}


def _fetch_vacancy_details(session: CdpSession, url: str, settle: float) -> Optional[dict]:
    try:
        session.navigate(url, settle=settle)
        data = session.evaluate(JS_VACANCY_FULL, timeout=15)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def search_once(
    store: QueueStore,
    *,
    clear_check: bool = False,
    on_progress: Optional[Callable[[str], None]] = None,
) -> Dict:
    cfg = load_config()
    threshold = int(cfg.get("score_threshold") or 70)
    url = cfg.get("hh_search_url")
    excludes = load_excludes(cfg)
    deep = bool(cfg.get("deep_score", True))
    settle = float(cfg.get("vacancy_settle_sec") or 1.1)
    if clear_check:
        max_pages = int(cfg.get("clear_check_max_pages") or 10)
        max_deep = 0
    else:
        max_pages = int(cfg.get("serp_max_pages") or 6)
        max_deep = int(cfg.get("deep_score_max") or 50)
    added = []
    skipped = 0
    deep_opened = 0
    serp_pages = 0
    t0 = time.time()

    from .preferences import hard_reject, search_seed_urls
    from .sphere_filter import hard_reject_out_of_sphere
    from .user_profile import load_profile

    activity_sphere = (load_profile().get("activity_sphere") or "").strip()

    seed_urls = search_seed_urls(url or "")
    if not seed_urls and url:
        seed_urls = [str(url)]

    if clear_check:
        cc_days = int(cfg.get("clear_check_days") or 7)
        seed_urls = [_with_search_period(u, cc_days) for u in seed_urls]

    per_vac = 18.0 if deep else 4.0
    # Extra SERP seeds (Desirable OR-query) need more chrome time
    fetch_timeout = float(cfg.get("clear_check_timeout_sec") or 900) if clear_check else max(
        360.0, 80.0 + max_deep * per_vac + 60.0 * max(0, len(seed_urls) - 1)
    )

    def prog(msg: str) -> None:
        if on_progress:
            on_progress(msg)

    prepared: List[dict] = []

    try:
        with chrome_exclusive(timeout=fetch_timeout):
            session = open_session(seed_urls[0] if seed_urls else url)
            try:
                cards: List[dict] = []
                seen_card_urls: set = set()
                need_login = False
                for seed_i, seed in enumerate(seed_urls or [url or ""], start=1):
                    if not seed:
                        continue
                    prog(f"SERP seed {seed_i}/{len(seed_urls)}…")
                    page_cards, serp_meta = _collect_serp_cards(
                        session, seed, max_pages, on_progress=prog
                    )
                    serp_pages += int(serp_meta.get("pages") or 0)
                    if serp_meta.get("needLogin"):
                        need_login = True
                        break
                    for c in page_cards:
                        link = norm_url(c.get("url") or "")
                        if not link or link in seen_card_urls:
                            continue
                        seen_card_urls.add(link)
                        cards.append(c)

                if need_login:
                    return {
                        "ok": False,
                        "error": "Нужен вход в HH. Нажмите «Войти в HH / Открыть Chrome» и залогиньтесь.",
                        "added": [],
                        "checked": 0,
                        "clear_check": clear_check,
                    }

                if clear_check:
                    serp_links = [norm_url(c.get("url") or "") for c in cards]
                    cleared = store.forget_seen(serp_links)
                    prog(f"Clear Check: сброшено seen для {cleared} URL с SERP")

                candidates: List[dict] = []
                for c in cards:
                    link = norm_url(c.get("url") or "")
                    if not link or link in excludes:
                        skipped += 1
                        continue
                    if store.in_queue(link):
                        skipped += 1
                        continue
                    if not clear_check:
                        if c.get("visited"):
                            skipped += 1
                            continue
                        if link in store.seen:
                            skipped += 1
                            continue
                    # Early Reject gate on SERP title+snippet (saves deep fetch)
                    title0 = (c.get("title") or "").strip()
                    snip0 = c.get("snippet") or ""
                    rejected, _rej = hard_reject(title0, snip0)
                    if rejected:
                        store.remember(link)
                        skipped += 1
                        prog(f"  reject: {title0[:50]}")
                        continue
                    rejected, _rej = hard_reject_out_of_sphere(
                        title0, snip0, sphere=activity_sphere
                    )
                    if rejected:
                        store.remember(link)
                        skipped += 1
                        prog(f"  sphere-reject: {title0[:50]}")
                        continue
                    candidates.append(c)

                if max_deep > 0:
                    candidates = candidates[: max(0, max_deep)]

                prog(f"К загрузке текста: {len(candidates)} карточек (пропущено {skipped})")

                for idx, c in enumerate(candidates, start=1):
                    link = norm_url(c.get("url") or "")
                    if not link or store.in_queue(link):
                        skipped += 1
                        continue
                    title = (c.get("title") or "").strip() or "Без названия"
                    company = (c.get("company") or "").strip()
                    salary = (c.get("salary") or "").strip()
                    schedule = "удалённо"
                    experience = ""
                    snippet = c.get("snippet") or ""

                    if deep:
                        if idx == 1 or idx == len(candidates) or idx % 5 == 0:
                            prog(f"[fetch {idx}/{len(candidates)}] {title[:60]}…")
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
                                "clear_check": clear_check,
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

                    rejected, rej_reasons = hard_reject(
                        title, snippet, schedule=schedule, experience=experience
                    )
                    if rejected:
                        store.remember(link)
                        skipped += 1
                        prog(f"  reject: {', '.join(rej_reasons[:3])}")
                        continue
                    rejected, rej_reasons = hard_reject_out_of_sphere(
                        title, snippet, sphere=activity_sphere
                    )
                    if rejected:
                        store.remember(link)
                        skipped += 1
                        prog(f"  sphere-reject: {', '.join(rej_reasons[:3])}")
                        continue

                    prepared.append(
                        {
                            "link": link,
                            "title": title,
                            "company": company,
                            "salary": salary,
                            "schedule": schedule,
                            "experience": experience,
                            "snippet": (snippet or "")[:8000],
                        }
                    )
            finally:
                session.close()

        if prepared:
            workers = max(1, min(int(cfg.get("cursor_score_workers") or 5), 6))
            prog(f"Cursor score: {len(prepared)} вакансий, workers={workers}…")
            scored = score_many_parallel(prepared, cfg=cfg, workers=workers, on_progress=prog)
        else:
            scored = []

        want_cursor_letter = bool(cfg.get("cover_letter_via_cursor", True)) and not bool(
            cfg.get("python_only", False)
        )
        from .cover_letter import _api_key as _letter_key

        has_letter_key = bool(_letter_key(cfg))

        for item in scored:
            link = item["link"]
            title = item["title"]
            company = item.get("company") or ""
            salary = item.get("salary") or ""
            schedule = item.get("schedule") or ""
            experience = item.get("experience") or ""
            snippet = item.get("snippet") or ""
            sc = int(item.get("score") or 0)
            ok = bool(item.get("accept_ok"))
            reasons = list(item.get("reasons") or [])
            score_meta = item.get("score_meta") or {}
            src = str(score_meta.get("source") or "rules")
            reasons = reasons + [f"score:{src}"]

            if text_looks_like_refusal(snippet, title) or (
                reasons and any("refusal" in r.lower() or "Отказ" in r for r in reasons)
            ):
                store.mark(link, "banned")
                skipped += 1
                continue
            if not ok or sc < threshold:
                store.remember(link)
                skipped += 1
                prog(f"  {sc}% — ниже порога {threshold}")
                continue

            full_text = (snippet or "")[:12000]
            if want_cursor_letter and has_letter_key:
                letter, letter_src = "", "pending"
            else:
                letter, letter_src = make_cover_letter(
                    title,
                    company=company,
                    description=full_text,
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
                description=full_text,
                status="new",
            )
            if store.add(v):
                added.append(v)
                prog(f"  +{sc}% → очередь: {title[:50]}")
            else:
                skipped += 1

        if added and want_cursor_letter and has_letter_key:
            # Письма пишет UI (параллельная очередь), здесь только помечаем pending.
            pass
    except TimeoutError as e:
        return {"ok": False, "error": str(e), "added": [], "checked": 0, "clear_check": clear_check}
    except CdpError as e:
        return {"ok": False, "error": str(e), "added": [], "checked": 0, "clear_check": clear_check}
    except Exception as e:
        return {"ok": False, "error": str(e), "added": [], "checked": 0, "clear_check": clear_check}

    elapsed = round(time.time() - t0, 1)
    result = {
        "ok": True,
        "added": added,
        "checked": skipped + len(added),
        "skipped": skipped,
        "deep_opened": deep_opened,
        "serp_pages": serp_pages,
        "elapsed_sec": elapsed,
        "error": "",
        "href": url or "",
        "letter_upgrade_urls": [v.url for v in added],
        "clear_check": clear_check,
    }
    try:
        append_event(
            "search",
            ok=True,
            elapsed_ms=int(elapsed * 1000),
            elapsed_sec=elapsed,
            added=len(added),
            checked=skipped + len(added),
            skipped=skipped,
            deep_opened=deep_opened,
            deep=bool(deep),
            clear_check=clear_check,
            serp_pages=serp_pages,
        )
    except Exception:
        pass
    return result


def upgrade_cover_letters(
    store: QueueStore,
    only_urls: Optional[set] = None,
    *,
    on_progress: Optional[Callable[[str], None]] = None,
) -> int:
    """Generate unique Cursor cover letters (parallel node workers)."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from .cover_letter import _api_key, is_stale_template

    cfg = load_config()
    want_cursor = bool(cfg.get("cover_letter_via_cursor", True)) and not bool(
        cfg.get("python_only", False)
    )
    has_key = bool(_api_key(cfg))
    workers = max(1, min(int(cfg.get("cursor_letter_workers") or 5), 6))
    lock = threading.Lock()
    todo: List[Vacancy] = []

    for v in list(store.items):
        if only_urls is not None and v.url not in only_urls:
            continue
        src = (v.letter_source or "").strip().lower()
        stale = is_stale_template(v.cover_letter or "")
        empty = not (v.cover_letter or "").strip()
        pending = src in ("", "pending", "local")
        need_cursor = want_cursor and has_key and src != "cursor"
        if not (empty or stale or pending or need_cursor):
            continue
        todo.append(v)

    if not todo:
        return 0

    def _one(v: Vacancy) -> tuple[str, Optional[str], Optional[str]]:
        letter, new_src = make_cover_letter(
            v.title,
            company=v.company,
            description=v.description or "",
            salary=v.salary,
            reasons=v.reasons,
            force_local=not (want_cursor and has_key),
        )
        return v.url, letter, new_src

    upgraded = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(_one, v) for v in todo]
        done_n = 0
        for fut in as_completed(futs):
            url, letter, new_src = fut.result()
            done_n += 1
            with lock:
                target = next((x for x in store.items if x.url == url), None)
                if not target:
                    continue
                if want_cursor and has_key and new_src != "cursor":
                    if not (target.cover_letter or "").strip() or (
                        target.letter_source or ""
                    ) == "pending":
                        target.letter_source = "pending"
                        store.save()
                    if on_progress:
                        on_progress(f"  письмо [{done_n}/{len(todo)}] pending: {target.title[:40]}")
                    continue
                if letter and (
                    letter != target.cover_letter or new_src != target.letter_source
                ):
                    target.cover_letter = letter
                    target.letter_source = new_src or "cursor"
                    upgraded += 1
                    store.save()
                    if on_progress:
                        on_progress(
                            f"  письмо [{done_n}/{len(todo)}] OK: {target.title[:40]}"
                        )
    return upgraded


def generate_one_letter(store: QueueStore, url: str) -> dict:
    """One Cursor cover letter. Used by the UI letter pump (parallel, incremental)."""
    from .cover_letter import _api_key, _via_cursor, make_cover_letter
    from .queue_store import norm_url as _nu

    cfg = load_config()
    nid = _nu(url)
    v = next((x for x in store.items if _nu(x.url) == nid), None)
    if not v:
        return {"ok": False, "url": url, "error": "нет в очереди"}
    want = bool(cfg.get("cover_letter_via_cursor", True)) and not bool(cfg.get("python_only", False))
    if want and _api_key(cfg):
        letter, meta = _via_cursor(
            title=v.title,
            company=v.company or "",
            description=v.description or "",
            salary=v.salary or "",
            reasons=list(v.reasons or []),
            cfg=cfg,
        )
        if letter:
            v.cover_letter = letter
            v.letter_source = "cursor"
            store.save()
            return {"ok": True, "url": v.url, "title": v.title}
        return {
            "ok": False,
            "url": v.url,
            "title": v.title,
            "error": str((meta or {}).get("error") or "Cursor не вернул письмо"),
        }
    letter, src = make_cover_letter(
        v.title,
        company=v.company,
        description=v.description or "",
        salary=v.salary,
        reasons=v.reasons,
        force_local=True,
    )
    if letter:
        v.cover_letter = letter
        v.letter_source = src or "local"
        store.save()
        return {"ok": True, "url": v.url, "title": v.title, "source": src}
    return {"ok": False, "url": v.url, "title": v.title, "error": "пустое письмо"}


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

    # 2) Ensure Cursor letter from full text before clipboard (no universal local).
    cfg = load_config()
    want_cursor = bool(cfg.get("cover_letter_via_cursor", True)) and not bool(
        cfg.get("python_only", False)
    )
    from .cover_letter import _api_key, make_cover_letter

    if want_cursor and _api_key(cfg) and (v.letter_source or "") != "cursor":
        letter, src = make_cover_letter(
            v.title,
            company=v.company,
            description=v.description or "",
            salary=v.salary,
            reasons=v.reasons,
            force_local=False,
        )
        if letter and src == "cursor":
            v.cover_letter = letter
            v.letter_source = "cursor"

    clip_ok = False
    if (v.cover_letter or "").strip():
        if (v.letter_source or "") == "cursor":
            clip_ok = set_clipboard(v.cover_letter or "")
        elif not want_cursor or not _api_key(cfg):
            clip_ok = set_clipboard(v.cover_letter or "")

    who = f"«{v.title}» — " if v.title else ""
    pending = want_cursor and (v.letter_source or "") != "cursor"
    if clip_ok:
        msg = f"{who}вкладка открыта, письмо Cursor в буфере (сам нажми «Откликнуться» → Ctrl+V)."
    elif pending:
        msg = f"{who}вкладка открыта. Письмо Cursor ещё не готово — дождитесь генерации."
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
        "letter_pending": pending or not bool((v.cover_letter or "").strip()),
        "message": msg,
    }


def _try_paste_cover_letter(url: str, letter: str, navigate: bool = False) -> None:
    """Устарело: автоклик «Откликнуться» отключён по запросу пользователя."""
    return
