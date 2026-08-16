# -*- coding: utf-8 -*-
"""Bench Cursor scoring + cover-letter generation (time + tokens)."""
from __future__ import annotations

import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from radar.config import load_config
from radar.cover_letter import BRIDGE as LETTER_BRIDGE, _api_key
from radar.cursor_score import score_for_search

SAMPLES = [
    {
        "title": "Frontend Vue 3 TypeScript",
        "company": "DataStream",
        "salary": "160000",
        "schedule": "remote",
        "snippet": "Middle Frontend Vue 3, TypeScript, Pinia, REST. Remote. 3+ years. Dashboards and tables.",
    },
    {
        "title": "Fullstack Node.js / Vue",
        "company": "NevaTech",
        "salary": "",
        "schedule": "remote",
        "snippet": "Fullstack: Node.js, NestJS, Vue 3. Remote. TypeScript required.",
    },
    {
        "title": "React developer",
        "company": "ReactOnly",
        "salary": "200000",
        "schedule": "remote",
        "snippet": "Only React and Next.js. No Vue. Remote.",
    },
    {
        "title": "Nuxt 3 developer",
        "company": "SSR Lab",
        "salary": "negotiable",
        "schedule": "remote",
        "snippet": "Nuxt 3, SSR, TypeScript. Junior+/Middle. Remote.",
    },
    {
        "title": "Vue 2 support engineer",
        "company": "LegacyCo",
        "salary": "140000",
        "schedule": "remote",
        "snippet": "Vue 2 SPA support, migration to Vue 3. Remote. Ag-Grid, dashboards.",
    },
]


def _avg(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return round(statistics.mean(vals), 1)


def _sum(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return int(sum(vals))


def _gen_letter_meta(sample: dict, reasons: list, cfg: dict) -> dict:
    key = _api_key(cfg)
    if not key or not LETTER_BRIDGE.exists():
        return {"ok": False, "error": "no key/bridge"}
    payload = {
        "title": sample["title"],
        "company": sample.get("company") or "",
        "description": sample.get("snippet") or "",
        "salary": sample.get("salary") or "",
        "reasons": reasons,
        "apiKey": key,
        "model": cfg.get("cursor_model") or "composer-2.5",
        "cwd": str(ROOT.parent),
        "returnMeta": True,
    }
    timeout = int(cfg.get("cover_letter_timeout_sec") or 90)
    t0 = time.perf_counter()
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", suffix=".json", delete=False
    ) as tf:
        json.dump(payload, tf, ensure_ascii=False)
        tmp = tf.name
    try:
        proc = subprocess.run(
            ["node", str(LETTER_BRIDGE), tmp],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=str(LETTER_BRIDGE.parent),
        )
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass
    wall = int((time.perf_counter() - t0) * 1000)
    raw = (proc.stdout or "").strip()
    if proc.returncode != 0 or not raw:
        return {
            "ok": False,
            "error": ((proc.stderr or raw) or "empty")[:300],
            "elapsed_ms": wall,
        }
    try:
        data = json.loads(raw)
    except Exception:
        return {"ok": False, "error": "bad json from letter bridge", "elapsed_ms": wall}
    usage = data.get("usage") or {}
    letter = data.get("letter") or ""
    return {
        "ok": bool(data.get("ok")),
        "elapsed_ms": int(data.get("elapsed_ms") or wall),
        "wall_ms": wall,
        "inputTokens": usage.get("inputTokens"),
        "outputTokens": usage.get("outputTokens"),
        "totalTokens": usage.get("totalTokens"),
        "letter_chars": len(letter),
        "source": "cursor",
    }


def _html(report: dict) -> str:
    score_rows = report.get("scoring") or []
    letter_rows = report.get("letters") or []
    s_ok = [r for r in score_rows if r.get("source") == "cursor"]
    l_ok = [r for r in letter_rows if r.get("ok")]

    def row_score(r):
        return (
            "<tr>"
            f"<td>{r.get('title')}</td>"
            f"<td>{r.get('score')}</td>"
            f"<td>{'yes' if r.get('accept') else 'no'}</td>"
            f"<td>{r.get('source')}</td>"
            f"<td>{r.get('elapsed_ms')}</td>"
            f"<td>{r.get('inputTokens')}</td>"
            f"<td>{r.get('outputTokens')}</td>"
            f"<td>{r.get('totalTokens')}</td>"
            f"<td>{'; '.join(r.get('reasons') or [])}</td>"
            "</tr>"
        )

    def row_letter(r):
        return (
            "<tr>"
            f"<td>{r.get('title')}</td>"
            f"<td>{'yes' if r.get('ok') else 'no'}</td>"
            f"<td>{r.get('elapsed_ms')}</td>"
            f"<td>{r.get('inputTokens')}</td>"
            f"<td>{r.get('outputTokens')}</td>"
            f"<td>{r.get('totalTokens')}</td>"
            f"<td>{r.get('letter_chars')}</td>"
            f"<td>{r.get('error') or ''}</td>"
            "</tr>"
        )

    summ = report.get("summary") or {}
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>
<title>VacancyRadar Cursor full bench</title>
<style>
body{{font-family:Segoe UI,sans-serif;background:#111827;color:#e5e7eb;margin:24px}}
h1,h2{{color:#5eead4}}table{{border-collapse:collapse;width:100%;font-size:14px;margin-bottom:28px}}
th,td{{border:1px solid #334155;padding:8px 10px;text-align:left;vertical-align:top}}
th{{background:#1f2937;color:#94a3b8}}.summary{{background:#1a2332;padding:16px;border-radius:8px;margin-bottom:20px}}
.note{{color:#94a3b8;font-size:13px}}
</style></head><body>
<h1>Cursor scoring + letters bench</h1>
<div class="summary">
<p><b>Model:</b> {summ.get('model')} | <b>Samples scored:</b> {summ.get('score_n')} | <b>Letters:</b> {summ.get('letter_n')}</p>
<p><b>Scoring avg:</b> {summ.get('score_avg_ms')} ms | tokens avg {summ.get('score_avg_tok')} (sum {summ.get('score_sum_tok')})</p>
<p><b>Letters avg:</b> {summ.get('letter_avg_ms')} ms | tokens avg {summ.get('letter_avg_tok')} (sum {summ.get('letter_sum_tok')})</p>
<p><b>Combined token sum:</b> {summ.get('combined_sum_tok')} | <b>Wall total:</b> {summ.get('wall_total_ms')} ms</p>
<p class="note">Generated by tools/bench_cursor_full.py - resume from cvddv.pdf + portfolio/github in score prompt.</p>
</div>
<h2>Scoring</h2>
<table><thead><tr>
<th>Vacancy</th><th>Score</th><th>Accept</th><th>Source</th>
<th>Elapsed ms</th><th>In</th><th>Out</th><th>Total</th><th>Reasons</th>
</tr></thead><tbody>{''.join(row_score(r) for r in score_rows)}</tbody></table>
<h2>Cover letters (accepted only)</h2>
<table><thead><tr>
<th>Vacancy</th><th>OK</th><th>Elapsed ms</th><th>In</th><th>Out</th><th>Total</th><th>Chars</th><th>Error</th>
</tr></thead><tbody>{''.join(row_letter(r) for r in letter_rows) or '<tr><td colspan="8">none accepted</td></tr>'}</tbody></table>
</body></html>"""


def main():
    cfg = dict(load_config())
    cfg["scoring_mode"] = "cursor"
    score_rows = []
    letter_rows = []
    wall0 = time.perf_counter()

    print("=== Cursor SCORE bench n=", len(SAMPLES), flush=True)
    for i, s in enumerate(SAMPLES, 1):
        print(f"[{i}/{len(SAMPLES)}] score: {s['title']} ...", flush=True)
        t0 = time.perf_counter()
        sc, reasons, ok, meta = score_for_search(
            title=s["title"],
            snippet=s["snippet"],
            salary_text=s.get("salary") or "",
            schedule=s.get("schedule") or "remote",
            company=s.get("company") or "",
            cfg=cfg,
        )
        wall = (time.perf_counter() - t0) * 1000
        usage = meta.get("usage") or {}
        row = {
            "title": s["title"],
            "score": sc,
            "accept": ok,
            "source": meta.get("source"),
            "elapsed_ms": meta.get("elapsed_ms") or round(wall),
            "wall_ms": round(wall),
            "inputTokens": usage.get("inputTokens"),
            "outputTokens": usage.get("outputTokens"),
            "totalTokens": usage.get("totalTokens"),
            "reasons": reasons,
            "sample": s,
        }
        score_rows.append(row)
        print(
            f"  -> {row['source']} score={sc} accept={ok} "
            f"ms={row['elapsed_ms']} tok={row['totalTokens']}",
            flush=True,
        )

    accepted = [r for r in score_rows if r.get("accept") and r.get("source") == "cursor"]
    print(f"=== Cursor LETTER bench n={len(accepted)}", flush=True)
    for i, r in enumerate(accepted, 1):
        s = r["sample"]
        print(f"[{i}/{len(accepted)}] letter: {s['title']} ...", flush=True)
        meta = _gen_letter_meta(s, r.get("reasons") or [], cfg)
        meta["title"] = s["title"]
        letter_rows.append(meta)
        print(
            f"  -> ok={meta.get('ok')} ms={meta.get('elapsed_ms')} "
            f"tok={meta.get('totalTokens')} chars={meta.get('letter_chars')}",
            flush=True,
        )

    # strip sample blobs from json dump
    for r in score_rows:
        r.pop("sample", None)

    s_ok = [r for r in score_rows if r.get("source") == "cursor"]
    l_ok = [r for r in letter_rows if r.get("ok")]
    summary = {
        "model": cfg.get("cursor_model") or "composer-2.5",
        "score_n": len(score_rows),
        "letter_n": len(letter_rows),
        "score_avg_ms": _avg([r.get("elapsed_ms") for r in s_ok]),
        "score_avg_tok": _avg([r.get("totalTokens") for r in s_ok]),
        "score_sum_tok": _sum([r.get("totalTokens") for r in s_ok]),
        "letter_avg_ms": _avg([r.get("elapsed_ms") for r in l_ok]),
        "letter_avg_tok": _avg([r.get("totalTokens") for r in l_ok]),
        "letter_sum_tok": _sum([r.get("totalTokens") for r in l_ok]),
        "combined_sum_tok": (_sum([r.get("totalTokens") for r in s_ok]) or 0)
        + (_sum([r.get("totalTokens") for r in l_ok]) or 0),
        "wall_total_ms": int((time.perf_counter() - wall0) * 1000),
    }
    report = {"summary": summary, "scoring": score_rows, "letters": letter_rows}

    out_dir = ROOT / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "cursor_full_bench.json"
    html_path = out_dir / "cursor_full_report.html"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(_html(report), encoding="utf-8")
    # also refresh score-only report for convenience
    (out_dir / "cursor_score_bench.json").write_text(
        json.dumps(score_rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("SUMMARY", json.dumps(summary, ensure_ascii=False), flush=True)
    print("Wrote", json_path, flush=True)
    print("Wrote", html_path, flush=True)


if __name__ == "__main__":
    main()
