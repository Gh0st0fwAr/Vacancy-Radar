# -*- coding: utf-8 -*-
"""Passive VacancyRadar stats watcher.

Does NOT call Cursor / spend tokens.
Reads radar_metrics.jsonl (+ legacy score metrics) and every hour appends
a last-hour summary to data/stats_watcher.txt (also prints to console).
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from radar.config import DATA
from radar.metrics_log import METRICS_PATH, read_events, read_legacy_score_events

LEGACY_SCORE = DATA / "cursor_score_metrics.jsonl"
OUT_LOG = DATA / "stats_watcher.txt"
STATE_PATH = DATA / "stats_watcher_state.json"
DEFAULT_INTERVAL_SEC = 3600


def _avg(vals: List[float]) -> Optional[float]:
    vals = [float(v) for v in vals if v is not None]
    if not vals:
        return None
    return round(statistics.mean(vals), 1)


def _sum_int(vals: List[Any]) -> int:
    total = 0
    for v in vals:
        if v is None:
            continue
        try:
            total += int(v)
        except Exception:
            pass
    return total


def _fmt_ms(ms: Optional[float]) -> str:
    if ms is None:
        return "n/a"
    if ms >= 1000:
        return f"{ms/1000:.1f}s ({int(ms)} ms)"
    return f"{int(ms)} ms"


def _fmt_tok(n: Optional[float]) -> str:
    if n is None:
        return "n/a"
    return f"{int(n):,}".replace(",", " ")


def collect_window(since_ts: float, until_ts: float) -> List[dict]:
    rows = read_events(METRICS_PATH, since_ts=since_ts)
    # Dedup legacy score rows that may already be mirrored into radar_metrics
    have_score_ts = {
        (round(float(r.get("ts") or 0), 2), str(r.get("title") or ""))
        for r in rows
        if r.get("kind") == "score"
    }
    for r in read_legacy_score_events(LEGACY_SCORE, since_ts=since_ts):
        key = (round(float(r.get("ts") or 0), 2), str(r.get("title") or ""))
        if key in have_score_ts:
            continue
        rows.append(r)
    return [r for r in rows if float(r.get("ts") or 0) <= until_ts]


def summarize(events: List[dict], *, since_ts: float, until_ts: float) -> str:
    searches = [e for e in events if e.get("kind") == "search"]
    scores = [e for e in events if e.get("kind") == "score"]
    letters = [e for e in events if e.get("kind") == "letter"]
    cursor_scores = [e for e in scores if str(e.get("source") or "").startswith("cursor")]
    cursor_letters = [e for e in letters if e.get("source") == "cursor"]
    local_letters = [e for e in letters if e.get("source") == "local"]

    score_tok = _sum_int([e.get("totalTokens") for e in cursor_scores])
    letter_tok = _sum_int([e.get("totalTokens") for e in cursor_letters])
    score_in = _sum_int([e.get("inputTokens") for e in cursor_scores])
    score_out = _sum_int([e.get("outputTokens") for e in cursor_scores])
    letter_in = _sum_int([e.get("inputTokens") for e in cursor_letters])
    letter_out = _sum_int([e.get("outputTokens") for e in cursor_letters])

    added = _sum_int([e.get("added") for e in searches])
    checked = _sum_int([e.get("checked") for e in searches])
    deep = _sum_int([e.get("deep_opened") for e in searches])

    start = datetime.fromtimestamp(since_ts).strftime("%Y-%m-%d %H:%M:%S")
    end = datetime.fromtimestamp(until_ts).strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        "=" * 64,
        f"VacancyRadar stats watcher | window {start} .. {end}",
        "PASSIVE: no Cursor API calls from watcher",
        "-" * 64,
        "SEARCH",
        f"  runs: {len(searches)} | vacancies checked: {checked} | added to queue: {added} | deep opened: {deep}",
        f"  avg duration: {_fmt_ms(_avg([e.get('elapsed_ms') for e in searches]))}",
        "SCORING",
        f"  events: {len(scores)} | cursor: {len(cursor_scores)} | other/fallback: {len(scores) - len(cursor_scores)}",
        f"  avg duration (cursor): {_fmt_ms(_avg([e.get('elapsed_ms') for e in cursor_scores]))}",
        f"  tokens (cursor): total {_fmt_tok(score_tok)} (in {_fmt_tok(score_in)} / out {_fmt_tok(score_out)})",
        f"  avg tokens / cursor score: {_fmt_tok(_avg([e.get('totalTokens') for e in cursor_scores]))}",
        "COVER LETTERS",
        f"  events: {len(letters)} | cursor: {len(cursor_letters)} | local: {len(local_letters)}",
        f"  avg duration (cursor): {_fmt_ms(_avg([e.get('elapsed_ms') for e in cursor_letters]))}",
        f"  avg duration (local): {_fmt_ms(_avg([e.get('elapsed_ms') for e in local_letters]))}",
        f"  tokens (cursor): total {_fmt_tok(letter_tok)} (in {_fmt_tok(letter_in)} / out {_fmt_tok(letter_out)})",
        f"  avg tokens / cursor letter: {_fmt_tok(_avg([e.get('totalTokens') for e in cursor_letters]))}",
        "TOTAL CURSOR TOKENS (score + letter)",
        f"  {_fmt_tok(score_tok + letter_tok)}",
        "=" * 64,
        "",
    ]
    return "\n".join(lines)


def append_report(text: str) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    with OUT_LOG.open("a", encoding="utf-8") as f:
        f.write(text)
        if not text.endswith("\n"):
            f.write("\n")


def dump_once(window_sec: int) -> str:
    until_ts = time.time()
    since_ts = until_ts - window_sec
    events = collect_window(since_ts, until_ts)
    text = summarize(events, since_ts=since_ts, until_ts=until_ts)
    append_report(text)
    return text


def run_loop(interval_sec: int, window_sec: int, once: bool) -> None:
    print("VacancyRadar stats watcher started", flush=True)
    print(f"  metrics: {METRICS_PATH}", flush=True)
    print(f"  log:     {OUT_LOG}", flush=True)
    print(f"  interval: {interval_sec}s | window: last {window_sec}s", flush=True)
    print("  mode: PASSIVE (does not call Cursor / spend tokens)", flush=True)
    text = dump_once(window_sec)
    print(text, flush=True)
    if once:
        return
    while True:
        time.sleep(max(5, interval_sec))
        text = dump_once(window_sec)
        print(text, flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Passive VacancyRadar hourly stats watcher")
    ap.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_SEC, help="Seconds between dumps (default 3600)")
    ap.add_argument("--window", type=int, default=DEFAULT_INTERVAL_SEC, help="Stats window seconds (default 3600)")
    ap.add_argument("--once", action="store_true", help="Dump one report and exit")
    args = ap.parse_args()
    run_loop(args.interval, args.window, args.once)


if __name__ == "__main__":
    main()
