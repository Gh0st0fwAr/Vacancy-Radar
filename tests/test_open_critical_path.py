# -*- coding: utf-8 -*-
"""Critical-path timing: Chrome open must not wait on PowerShell clipboard."""
from __future__ import annotations

import threading
import time
from unittest.mock import patch

from radar.clipboard_util import set_clipboard, set_clipboard_async
from radar.queue_store import Vacancy, QueueStore


class TestClipboardFastPath:
    def test_winapi_preferred_over_powershell(self):
        order = []

        def winapi(text):
            order.append("winapi")
            return True

        def clip(text):
            order.append("clip")
            return True

        def ps(text):
            order.append("powershell")
            return True

        with patch("radar.clipboard_util._via_winapi", side_effect=winapi):
            with patch("radar.clipboard_util._via_clip_exe", side_effect=clip):
                with patch("radar.clipboard_util._via_powershell", side_effect=ps):
                    assert set_clipboard("hello") is True
        assert order == ["winapi"]
        assert "powershell" not in order

    def test_async_returns_immediately(self):
        def slow(_text):
            time.sleep(0.3)
            return True

        with patch("radar.clipboard_util.set_clipboard", side_effect=slow):
            t0 = time.perf_counter()
            set_clipboard_async("x" * 100)
            elapsed = time.perf_counter() - t0
        assert elapsed < 0.1


class TestOpenVacancyCriticalPath:
    def test_chrome_not_blocked_by_slow_clipboard_async(self):
        """Async clipboard must not delay chrome thread completion."""

        def slow_clipboard(text):
            time.sleep(0.4)
            return True

        holder = {"ok": False, "ms": 0.0}

        def chrome_job():
            t0 = time.perf_counter()
            time.sleep(0.02)
            holder["ok"] = True
            holder["ms"] = (time.perf_counter() - t0) * 1000.0

        with patch("radar.clipboard_util.set_clipboard", side_effect=slow_clipboard):
            th = threading.Thread(target=chrome_job, daemon=True)
            t0 = time.perf_counter()
            th.start()
            set_clipboard_async("letter body")
            th.join(timeout=1.0)
            wall = (time.perf_counter() - t0) * 1000.0

        assert holder["ok"] is True
        assert holder["ms"] < 100
        assert wall < 200


class TestSetActivePersist:
    def test_persist_false_skips_disk(self, tmp_path, monkeypatch):
        q = tmp_path / "queue.json"
        s = tmp_path / "seen.json"
        q.write_text('{"items":[],"pointer":0,"active_url":""}', encoding="utf-8")
        s.write_text("[]", encoding="utf-8")
        monkeypatch.setattr("radar.queue_store.QUEUE_PATH", q)
        monkeypatch.setattr("radar.queue_store.SEEN_PATH", s)
        store = QueueStore(autoload=True)
        store.items = [
            Vacancy(
                id="1",
                title="T",
                company="C",
                url="https://hh.ru/vacancy/1",
                score=80,
            )
        ]
        mtime1 = q.stat().st_mtime_ns
        time.sleep(0.02)
        store.set_active(store.items[0].url, persist=False)
        mtime2 = q.stat().st_mtime_ns
        assert store.active_url.endswith("/1")
        assert mtime1 == mtime2
