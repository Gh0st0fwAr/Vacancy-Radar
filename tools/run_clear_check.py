# -*- coding: utf-8 -*-
"""CLI: run Clear Check (full SERP rescore). Usage: python tools/run_clear_check.py"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from radar.chrome_ctl import launch_chrome_for_login
from radar.queue_store import QueueStore
from radar.search_hh import search_once


def main() -> int:
    print("Launching Chrome / HH session…")
    print(launch_chrome_for_login(open_login=True))
    store = QueueStore()
    before = sum(1 for v in store.items if v.status == "new")
    print(f"Queue new before: {before}")

    def prog(msg: str) -> None:
        print(msg, flush=True)

    result = search_once(store, clear_check=True, on_progress=prog)
    added = result.get("added") or []
    after = sum(1 for v in store.items if v.status == "new")
    print("---")
    print(f"ok={result.get('ok')} added={len(added)} new_in_queue={after - before}")
    print(f"deep={result.get('deep_opened')} serp_pages={result.get('serp_pages')} elapsed={result.get('elapsed_sec')}s")
    if not result.get("ok"):
        print("error:", result.get("error"))
        return 1
    for v in added:
        print(f"  +{v.score}% {v.title} — {v.url}")
    return 0 if len(added) >= 2 else 2


if __name__ == "__main__":
    raise SystemExit(main())
