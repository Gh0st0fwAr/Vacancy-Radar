# -*- coding: utf-8 -*-
"""Analyze latest designer Clear Check → JSON (agent) + MD + HTML (human)."""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT_DIR = DATA / "analysis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MANAGER_RE = re.compile(
    r"(?i)менеджер|manager|руководитель|директор|sales|продаж|"
    r"account\s*manager|координатор|ассистент\s+руковод|проджект|project\s*manager|"
    r"product\s*manager|маркетолог|seo-?специалист"
)
DESIGN_RE = re.compile(
    r"(?i)дизайн|design|illustrat|фигма|figma|инфографик|"
    r"арт[-\s]?директор|художник|графич|креатив|motion|"
    r"ui/?ux|ux/?ui|баннер|логотип|бренд[-\s]?дизайн|карточк|"
    r"merch\s*design|3d\s*artist|3d-?модел|video-?editor|рисова"
)


def classify(title: str) -> list[str]:
    t = title or ""
    tags: list[str] = []
    if DESIGN_RE.search(t):
        tags.append("designish")
    if MANAGER_RE.search(t):
        tags.append("managerish")
    if re.search(
        r"(?i)разработчик|developer|программист|frontend|backend|fullstack|"
        r"golang|devops|vue|react|java\b|python|ruby",
        t,
    ):
        tags.append("devish")
    if re.search(r"(?i)продаж|sales\s*manager|телемаркетолог", t):
        tags.append("salesish")
    if not tags:
        tags.append("other")
    return tags


def esc(s: object) -> str:
    return (
        str(s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def pills(tags: list[str]) -> str:
    return " ".join(f'<span class="tag">{esc(t)}</span>' for t in tags)


def main() -> None:
    from radar.preferences import hard_reject, load_preferences
    from radar.sphere_filter import hard_reject_out_of_sphere

    log_lines = (DATA / "radar.log").read_text(encoding="utf-8", errors="replace").splitlines()
    starts = [i for i, l in enumerate(log_lines) if "Clear Check: SERP" in l]
    ends = [i for i, l in enumerate(log_lines) if "Clear Check OK." in l]
    end_idx = ends[-1]
    start_idx = max(s for s in starts if s < end_idx)
    session = log_lines[start_idx : end_idx + 1]
    summary = session[-1]
    load_line = next((l for l in session if "К загрузке текста" in l), "")

    added = checked = serp = deep = elapsed = None
    m = re.search(
        r"Новых:\s*(\d+),\s*проверено:\s*(\d+),\s*SERP[^:]*:\s*(\d+),\s*deep:\s*(\d+),\s*([\d.]+)",
        summary,
    )
    if m:
        added, checked, serp, deep, elapsed = m.groups()

    sphere_rej = [
        l.split("sphere-reject:", 1)[1].strip()
        for l in session
        if "sphere-reject:" in l
    ]
    kw_rej = [
        re.sub(r"^\s*reject:\s*", "", l).strip()
        for l in session
        if ("reject:" in l and "sphere-reject" not in l)
    ]
    # Log only prints every 5th fetch — incomplete. Prefer metrics titles.
    fetch_log = []
    for l in session:
        fm = re.search(r"\[fetch\s+\d+/\d+\]\s+(.+?)(?:…|\.\.\.|$)", l)
        if fm:
            fetch_log.append(fm.group(1).strip())

    metrics: list[dict] = []
    mp = DATA / "cursor_score_metrics.jsonl"
    if mp.exists():
        for line in mp.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                metrics.append(json.loads(line))
            except Exception:
                pass

    # Session wall clock Moscow 20:36–20:53 ≈ UTC 17:36–17:53 on 2026-08-19
    t0 = datetime(2026, 8, 19, 17, 36, tzinfo=timezone.utc).timestamp()
    t1 = datetime(2026, 8, 19, 17, 54, tzinfo=timezone.utc).timestamp()
    window = [m for m in metrics if t0 <= float(m.get("ts") or 0) <= t1]
    batch = [m for m in window if m.get("source") == "cursor"]

    prefs = load_preferences()
    sphere = "Дизайнер"
    titles = [(m.get("title") or "") for m in batch]

    mgr_titles = [t for t in titles if MANAGER_RE.search(t)]
    design_titles = [t for t in titles if DESIGN_RE.search(t)]
    nondesign_titles = [t for t in titles if not DESIGN_RE.search(t)]

    def replay(title_list: list[str]) -> list[dict]:
        out = []
        for t in title_list:
            r1, a1 = hard_reject(t, "")
            r2, a2 = hard_reject_out_of_sphere(t, "", sphere)
            out.append(
                {
                    "title": t,
                    "kw_reject": r1,
                    "kw_reasons": a1,
                    "sphere_reject": r2,
                    "sphere_reasons": a2,
                    "would_score": (not r1 and not r2),
                    "tags": classify(t),
                }
            )
        return out

    mgr_replay = replay(mgr_titles)
    nd_replay = replay(nondesign_titles)

    score_hist: Counter = Counter()
    for m in batch:
        s = int(m.get("score") or 0)
        score_hist[f"{(s // 10) * 10}-{(s // 10) * 10 + 9}"] += 1

    low20 = [m for m in batch if int(m.get("score") or 0) < 20]
    low35 = [m for m in batch if int(m.get("score") or 0) <= 35]
    pass70 = [m for m in batch if int(m.get("score") or 0) >= 70]

    def tag_stats(items: list[dict]) -> dict:
        c: Counter = Counter()
        for m in items:
            for t in classify(m.get("title") or ""):
                c[t] += 1
        return dict(c)

    low_sample = []
    for m in sorted(low35, key=lambda x: (int(x.get("score") or 0), x.get("title") or "")):
        title = m.get("title") or ""
        r1, a1 = hard_reject(title, "")
        r2, a2 = hard_reject_out_of_sphere(title, "", sphere)
        low_sample.append(
            {
                "title": title,
                "score": m.get("score"),
                "reasons": (m.get("reasons") or [])[:5],
                "tags": classify(title),
                "title_kw_reject": r1,
                "title_sphere_reject": r2,
                "kw_reasons": a1,
                "sphere_reasons": a2,
            }
        )

    cfg = json.loads((DATA / "config.json").read_text(encoding="utf-8"))
    hh = cfg.get("hh_search_url", "")
    text_q = unquote(parse_qs(urlparse(hh).query).get("text", [""])[0])
    profile = json.loads((DATA / "user_profile.json").read_text(encoding="utf-8"))

    deep_n = int(deep or 0)
    cursor_n = len(batch)
    secondary_drop_est = max(0, deep_n - cursor_n)

    analysis = {
        "meta": {
            "label": "design-clear-check-2026-08-19-2034",
            "aliases": [
                "логи по дизайну",
                "давай логи по дизайну",
                "design logs",
                "clear check дизайн",
                "настя дизайн лог",
            ],
            "session_start": session[0],
            "session_end": summary,
            "log_slice": [start_idx, end_idx],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "hh_search_text": text_q,
            "activity_sphere": profile.get("activity_sphere"),
            "portfolio_url": profile.get("portfolio_url"),
            "summary": {
                "added": added,
                "checked": checked,
                "serp_pages": serp,
                "deep": deep,
                "elapsed_sec": elapsed,
                "load_line": load_line,
                "cursor_scored": cursor_n,
                "secondary_drop_before_cursor_est": secondary_drop_est,
                "serp_sphere_reject": len(sphere_rej),
                "reject_log_lines": len(kw_rej),
            },
        },
        "funnel": {
            "note": "SERP dual-seed → primary gates on SERP card → deep fetch → secondary gates → Cursor",
            "to_deep": deep_n,
            "cursor_scored": cursor_n,
            "queue_added": int(added or 0),
            "sphere_reject_serp_logged": len(sphere_rej),
            "reject_lines_logged": len(kw_rej),
        },
        "cursor_batch": {
            "size": cursor_n,
            "histogram": dict(sorted(score_hist.items())),
            "below_20": len(low20),
            "below_or_eq_35": len(low35),
            "ge_70": len(pass70),
            "managerish": len(mgr_titles),
            "designish": len(design_titles),
            "nondesign": len(nondesign_titles),
            "low_tag_stats": tag_stats(low35),
            "mgr_still_pass_title_gates": sum(1 for x in mgr_replay if x["would_score"]),
            "nondesign_still_pass_title_gates": sum(1 for x in nd_replay if x["would_score"]),
            "low_title_killable_now": sum(
                1
                for x in low_sample
                if x["title_kw_reject"] or x["title_sphere_reject"]
            ),
            "manager_titles": mgr_titles,
            "nondesign_titles_sample": nondesign_titles[:80],
            "designish_titles": design_titles,
            "low_score_sample": low_sample[:80],
            "top_scores": sorted(
                [
                    {"score": m.get("score"), "title": m.get("title"), "reasons": (m.get("reasons") or [])[:3]}
                    for m in batch
                ],
                key=lambda x: -int(x["score"] or 0),
            )[:15],
        },
        "preferences_snapshot": prefs,
        "answers": {
            "q1_managers": [
                "Dual SERP: sphere seeds + Desirable OR (маркетплейс/WB/Ozon/Figma/гибрид/Москва) тянут менеджеров из description.",
                "Reject слишком узкий: «менеджер по продажам» есть, голого «менеджер»/«руководитель» без design-исключения нет.",
                "Sphere designer = thin blacklist (dev/salesy), не allowlist роли дизайнера.",
                f"В Cursor-батче менеджерских title: {len(mgr_titles)}; title-гейты сейчас всё ещё пропускают {sum(1 for x in mgr_replay if x['would_score'])}.",
            ],
            "q2_nondesign": [
                "Нет positive allowlist по title для sphere=Дизайнер.",
                f"Без design-сигнала в title: {len(nondesign_titles)} / {cursor_n} Cursor-скоров.",
                "Desirable-ключи про локацию/формат/маркетплейс ≠ роль дизайнера.",
                "Undesirable (frontend) не режет SERP — только мягко влияет на Cursor.",
            ],
            "q3_low_scores": [
                f"Cursor scored {cursor_n} из deep={deep_n}; ~{secondary_drop_est} отсеялись secondary reject/sphere после полного текста без SDK.",
                f"Из Cursor: ≤35% = {len(low35)}, <20% = {len(low20)}, ≥70% = {len(pass70)} — Cursor в основном прав, но поздно.",
                "Primary/secondary смотрят keyword+blacklist, не «обязан быть дизайн».",
                f"Title-killable текущими правилами среди low: {sum(1 for x in low_sample if x['title_kw_reject'] or x['title_sphere_reject'])}/{len(low_sample)} — значит большинство low легальны для нынешних гейтов.",
            ],
            "q4_speedup": [
                "Allowlist title до deep: дизайн-сигнал обязателен.",
                "Reject: менеджер/руководитель/маркетолог/SMM/рекрутер/координатор/оператор без design-слова.",
                "Desirable: убрать Москва/гибрид/115000/на руки/голый маркетплейс; Desirable SERP → search_field=name.",
                "References: 3–5 живых FIT карточек; в профиле якоря «карточки WB/Ozon, инфографика, Figma/PS».",
                "Снизить deep_score_max пока префильтр слабый; pre-Cursor title gate.",
            ],
        },
    }

    stem = "design_clearcheck_2026-08-19"
    json_path = OUT_DIR / f"{stem}.json"
    json_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        f"# {analysis['meta']['label']}",
        "",
        f"aliases: {analysis['meta']['aliases']}",
        f"summary: {analysis['meta']['summary']}",
        f"hh_text: {text_q}",
        "",
        "## Answers",
    ]
    for k, lines in analysis["answers"].items():
        md.append(f"### {k}")
        md.extend(f"- {x}" for x in lines)
        md.append("")
    md.append("## Histogram")
    md.append(str(analysis["cursor_batch"]["histogram"]))
    md.append("## Low sample")
    for x in low_sample[:40]:
        md.append(
            f"- {x['score']}% {x['tags']} | {x['title'][:100]} | "
            f"kw={x['title_kw_reject']} sph={x['title_sphere_reject']}"
        )
    md_path = OUT_DIR / f"{stem}.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    rows_mgr = "\n".join(
        f"<tr><td>{esc(t)}</td><td>{pills(classify(t))}</td></tr>" for t in mgr_titles[:40]
    )
    rows_nd = "\n".join(
        f"<tr><td>{esc(t)}</td><td>{pills(classify(t))}</td></tr>" for t in nondesign_titles[:45]
    )
    rows_low = []
    for x in low_sample[:50]:
        kill = "да" if (x["title_kw_reject"] or x["title_sphere_reject"]) else "нет"
        reasons = "; ".join(list(map(str, x.get("reasons") or []))[:2])
        rows_low.append(
            "<tr>"
            f"<td class='score'>{esc(x['score'])}%</td>"
            f"<td>{esc(x['title'])}</td>"
            f"<td>{pills(x['tags'])}</td>"
            f"<td>{kill}</td>"
            f"<td>{esc(reasons)}</td>"
            "</tr>"
        )
    hist_html = "".join(
        f"<div class='bar'><span>{esc(k)}</span>"
        f"<i style='width:{max(4, int(v) * 4)}px'></i><b>{v}</b></div>"
        for k, v in sorted(score_hist.items())
    )
    top_html = "\n".join(
        f"<li><b>{esc(x['score'])}%</b> — {esc(x['title'])}</li>"
        for x in analysis["cursor_batch"]["top_scores"][:10]
    )
    a = analysis["answers"]

    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Логи Clear Check — дизайн</title>
<style>
:root {{ --bg:#f3efe6; --ink:#1c1a16; --muted:#5c574c; --card:#fffdf8; --line:#d9d0c0; --accent:#0f6b5c; --warn:#a33b2b; --chip:#e7efe9; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; font:16px/1.45 "Segoe UI",sans-serif; color:var(--ink);
  background: radial-gradient(1100px 480px at 8% -8%, #dfece7, transparent 55%), var(--bg); }}
.wrap {{ max-width:1080px; margin:0 auto; padding:32px 20px 64px; }}
.eyebrow {{ color:var(--accent); font-weight:700; letter-spacing:.04em; text-transform:uppercase; font-size:12px; }}
h1 {{ margin:8px 0 10px; font-size:clamp(1.55rem,3vw,2.15rem); line-height:1.15; }}
.lede {{ color:var(--muted); max-width:68ch; }}
.stats {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(140px,1fr)); gap:12px; margin:20px 0; }}
.stat {{ background:var(--card); border:1px solid var(--line); border-radius:14px; padding:14px 16px; }}
.stat b {{ display:block; font-size:1.4rem; }}
.stat span {{ color:var(--muted); font-size:13px; }}
section {{ background:var(--card); border:1px solid var(--line); border-radius:18px; padding:22px; margin:16px 0; }}
h2 {{ margin:0 0 10px; font-size:1.22rem; }}
h3 {{ margin:16px 0 8px; font-size:1rem; }}
.tag {{ display:inline-block; background:var(--chip); border-radius:999px; padding:2px 8px; font-size:12px; margin:1px 2px; }}
table {{ width:100%; border-collapse:collapse; font-size:14px; }}
th,td {{ text-align:left; padding:8px 6px; border-bottom:1px solid var(--line); vertical-align:top; }}
th {{ color:var(--muted); font-size:12px; text-transform:uppercase; }}
.score {{ font-weight:700; color:var(--warn); white-space:nowrap; }}
.bar {{ display:flex; align-items:center; gap:10px; margin:5px 0; font-size:13px; }}
.bar span {{ width:64px; color:var(--muted); }}
.bar i {{ display:block; height:10px; background:var(--accent); border-radius:6px; opacity:.8; }}
.callout {{ border-left:4px solid var(--accent); background:#f3faf7; padding:8px 12px; border-radius:0 10px 10px 0; margin:12px 0; }}
.warnbox {{ border-left:4px solid var(--warn); background:#fbf3f1; padding:8px 12px; border-radius:0 10px 10px 0; margin:12px 0; }}
code {{ background:#efe9dc; padding:1px 5px; border-radius:4px; }}
.two {{ display:grid; grid-template-columns:1.1fr .9fr; gap:16px; }}
@media (max-width:820px){{ .two {{ grid-template-columns:1fr; }} }}
footer {{ color:var(--muted); font-size:13px; margin-top:24px; }}
</style></head><body><div class="wrap">
<header>
  <div class="eyebrow">VacancyRadar · Clear Check · Дизайнер</div>
  <h1>Почему проходит шум и куда уходит ~{esc(elapsed)}с</h1>
  <p class="lede">
    {esc(summary)} · до deep: <code>{esc(load_line)}</code><br/>
    Primary HH text: <code>{esc(text_q)}</code>
  </p>
  <div class="stats">
    <div class="stat"><b>{esc(deep)}</b><span>deep fetch</span></div>
    <div class="stat"><b>{esc(cursor_n)}</b><span>Cursor score</span></div>
    <div class="stat"><b>{esc(len(mgr_titles))}</b><span>менеджерских title</span></div>
    <div class="stat"><b>{esc(len(nondesign_titles))}</b><span>без design-сигнала</span></div>
    <div class="stat"><b>{esc(len(low35))}</b><span>score ≤35%</span></div>
    <div class="stat"><b>{esc(len(pass70))}</b><span>score ≥70%</span></div>
  </div>
</header>

<section id="q1"><h2>1. Почему много менеджеров на первичном?</h2>
<div class="warnbox">Узкий reject + широкий Desirable SERP + sphere без allowlist роли.</div>
<ul>{''.join(f'<li>{esc(x)}</li>' for x in a['q1_managers'])}</ul>
<h3>Менеджерские title в Cursor-батче</h3>
<table><thead><tr><th>Title</th><th>Теги</th></tr></thead><tbody>{rows_mgr}</tbody></table>
</section>

<section id="q2"><h2>2. Почему много не-дизайна?</h2>
<div class="callout">Система лучше говорит «это golang» чем «это обязано быть дизайном».</div>
<ul>{''.join(f'<li>{esc(x)}</li>' for x in a['q2_nondesign'])}</ul>
<h3>Без design-сигнала</h3>
<table><thead><tr><th>Title</th><th>Теги</th></tr></thead><tbody>{rows_nd}</tbody></table>
</section>

<section id="q3"><h2>3. Скоры &lt;20–35% у Cursor</h2>
<div class="two"><div>
<ul>{''.join(f'<li>{esc(x)}</li>' for x in a['q3_low_scores'])}</ul>
<h3>Топ скоров сессии</h3>
<ol>{top_html}</ol>
</div><div><h3>Гистограмма</h3>{hist_html}</div></div>
<h3>Низкие score</h3>
<table><thead><tr><th>Score</th><th>Title</th><th>Теги</th><th>Title уже режется?</th><th>Reasons</th></tr></thead>
<tbody>{''.join(rows_low)}</tbody></table>
</section>

<section id="q4"><h2>4. Ускорение и ужесточение</h2>
<ul>{''.join(f'<li>{esc(x)}</li>' for x in a['q4_speedup'])}</ul>
</section>

<footer>
Файлы: <code>data/analysis/{stem}.json</code>, <code>.md</code>, <code>.html</code>.
Алиас в чате: «логи по дизайну». {esc(analysis['meta']['created_at'])}
</footer>
</div></body></html>
"""
    html_path = OUT_DIR / f"{stem}.html"
    html_path.write_text(html, encoding="utf-8")

    pointer = {
        "label": analysis["meta"]["label"],
        "aliases": analysis["meta"]["aliases"],
        "path_json": f"data/analysis/{stem}.json",
        "path_md": f"data/analysis/{stem}.md",
        "path_html": f"data/analysis/{stem}.html",
        "created_at": analysis["meta"]["created_at"],
    }
    (OUT_DIR / "LATEST_DESIGN_LOG.json").write_text(
        json.dumps(pointer, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(pointer, ensure_ascii=False, indent=2))
    print(
        "cursor",
        cursor_n,
        "mgr",
        len(mgr_titles),
        "nondesign",
        len(nondesign_titles),
        "low35",
        len(low35),
        "ge70",
        len(pass70),
        "deep",
        deep,
    )


if __name__ == "__main__":
    main()
