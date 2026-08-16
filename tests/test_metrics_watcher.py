# -*- coding: utf-8 -*-
import importlib.util
import time
from pathlib import Path

from radar.metrics_log import append_event, read_events


def test_append_and_read(tmp_path, monkeypatch):
    path = tmp_path / "m.jsonl"
    monkeypatch.setattr("radar.metrics_log.METRICS_PATH", path)
    append_event("search", elapsed_ms=1200, added=2, checked=10)
    append_event(
        "score",
        title="Vue",
        source="cursor",
        elapsed_ms=9000,
        usage={"inputTokens": 100, "outputTokens": 20, "totalTokens": 120},
    )
    append_event(
        "letter",
        title="Vue",
        source="cursor",
        elapsed_ms=11000,
        usage={"inputTokens": 200, "outputTokens": 50, "totalTokens": 250},
    )
    rows = read_events(path)
    assert len(rows) == 3
    assert rows[0]["kind"] == "search"
    assert rows[1]["totalTokens"] == 120
    assert rows[2]["totalTokens"] == 250


def test_watcher_summarize_smoke():
    root = Path(__file__).resolve().parents[1]
    path = root / "tools" / "radar_stats_watcher.py"
    spec = importlib.util.spec_from_file_location("radar_stats_watcher", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    now = time.time()
    events = [
        {
            "ts": now - 10,
            "kind": "search",
            "elapsed_ms": 5000,
            "added": 1,
            "checked": 5,
            "deep_opened": 2,
        },
        {
            "ts": now - 5,
            "kind": "score",
            "source": "cursor",
            "elapsed_ms": 8000,
            "inputTokens": 1000,
            "outputTokens": 100,
            "totalTokens": 1100,
        },
        {
            "ts": now - 1,
            "kind": "letter",
            "source": "cursor",
            "elapsed_ms": 12000,
            "inputTokens": 2000,
            "outputTokens": 200,
            "totalTokens": 2200,
        },
    ]
    text = mod.summarize(events, since_ts=now - 3600, until_ts=now)
    assert "SEARCH" in text
    assert "SCORING" in text
    assert "COVER LETTERS" in text
    assert "3 300" in text or "3300" in text
