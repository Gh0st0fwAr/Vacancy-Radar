# -*- coding: utf-8 -*-
"""Minimal Chrome DevTools Protocol client (no Selenium)."""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Any, Optional

from websocket import WebSocketTimeoutException, create_connection

from .chrome_ctl import debug_port, _port_open, open_url_fast, launch_chrome_for_login, cdp_ws_ok


class CdpError(RuntimeError):
    pass


def _http(url: str, method: str = "GET", timeout: float = 3.0) -> Any:
    req = urllib.request.Request(url, method=method, data=b"" if method == "PUT" else None)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return raw


def ensure_debug_chrome(open_login: bool = False) -> int:
    port = debug_port()
    if not _port_open(port) or not cdp_ws_ok(port):
        launch_chrome_for_login(open_login=open_login or True)
        for _ in range(40):
            if _port_open(port, timeout=0.1) and cdp_ws_ok(port):
                break
            time.sleep(0.15)
    if not _port_open(port):
        raise CdpError(f"Chrome Radar не запущен (порт {port})")
    if not cdp_ws_ok(port):
        raise CdpError(
            "Chrome запущен, но CDP WebSocket закрыт. "
            "Нажмите «Войти в HH / Открыть Chrome» ещё раз."
        )
    return port


def list_tabs(port: Optional[int] = None) -> list:
    port = port or debug_port()
    data = _http(f"http://127.0.0.1:{port}/json/list", timeout=2.0)
    return data if isinstance(data, list) else []


def _new_tab(port: int, url: str) -> Optional[dict]:
    encoded = urllib.parse.quote(url, safe="")
    for target in (url, encoded):
        for method in ("PUT", "GET"):
            try:
                data = _http(f"http://127.0.0.1:{port}/json/new?{target}", method=method, timeout=3.0)
                if isinstance(data, dict) and data.get("webSocketDebuggerUrl"):
                    return data
            except Exception:
                continue
    open_url_fast(url, port)
    time.sleep(0.6)
    for tab in list_tabs(port):
        if url.split("?")[0] in (tab.get("url") or ""):
            return tab
    return None


def _pick_tab(port: int, url: str = "about:blank") -> dict:
    for tab in list_tabs(port):
        if tab.get("type") == "page" and tab.get("webSocketDebuggerUrl"):
            turl = tab.get("url") or ""
            if "chrome://" in turl or "devtools://" in turl:
                continue
            return tab
    tab = _new_tab(port, url)
    if not tab or not tab.get("webSocketDebuggerUrl"):
        raise CdpError("Не удалось открыть вкладку Chrome")
    return tab


class CdpSession:
    def __init__(self, ws_url: str, timeout: float = 12.0):
        self.ws = create_connection(ws_url, timeout=timeout)
        self.ws.settimeout(timeout)
        self._id = 0

    def close(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass

    def call(self, method: str, params: Optional[dict] = None, timeout: float = 12.0) -> Any:
        self._id += 1
        msg_id = self._id
        self.ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                raw = self.ws.recv()
            except WebSocketTimeoutException:
                continue
            except Exception as e:
                raise CdpError(f"CDP recv failed: {e}") from e
            try:
                data = json.loads(raw)
            except Exception:
                continue
            if data.get("id") != msg_id:
                continue
            if "error" in data:
                raise CdpError(str(data["error"]))
            return data.get("result")
        raise CdpError(f"CDP timeout: {method}")

    def evaluate(self, expression: str, timeout: float = 12.0) -> Any:
        result = self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": True,
            },
            timeout=timeout,
        )
        if not result:
            return None
        if result.get("exceptionDetails"):
            raise CdpError(str(result["exceptionDetails"]))
        return (result.get("result") or {}).get("value")

    def navigate(self, url: str, settle: float = 2.0) -> None:
        try:
            self.call("Page.enable", {}, timeout=5)
        except Exception:
            pass
        try:
            self.call("Page.navigate", {"url": url}, timeout=10)
        except CdpError:
            # Sometimes navigate response is dropped under event flood — still wait
            pass
        time.sleep(settle)
        # soft wait for body
        for _ in range(10):
            try:
                ready = self.evaluate(
                    "document.body && document.body.innerText ? document.body.innerText.length : 0",
                    timeout=3,
                )
                if isinstance(ready, (int, float)) and ready > 50:
                    return
            except Exception:
                pass
            time.sleep(0.4)


def open_session(start_url: str = "https://hh.ru/") -> CdpSession:
    port = ensure_debug_chrome(open_login=False)
    tab = _pick_tab(port, start_url)
    ws = tab.get("webSocketDebuggerUrl")
    if not ws:
        raise CdpError("Нет webSocketDebuggerUrl у вкладки")
    return CdpSession(ws, timeout=12)


def open_and_eval(url: str, expression: str, settle: float = 1.8) -> Any:
    session = open_session(url)
    try:
        session.navigate(url, settle=settle)
        return session.evaluate(expression, timeout=15)
    finally:
        session.close()


def navigate_only(url: str, settle: float = 1.2) -> None:
    session = open_session(url)
    try:
        session.navigate(url, settle=settle)
    finally:
        session.close()
