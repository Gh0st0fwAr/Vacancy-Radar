# -*- coding: utf-8 -*-
"""Launch / attach Chrome with dedicated VacancyRadar profile (fast paths)."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

from .config import CHROME_PROFILE, load_config

HH_LOGIN = "https://hh.ru/account/login"
HH_HOME = "https://hh.ru/"

_driver_lock = threading.RLock()
_cached_driver = None
_cached_port: Optional[int] = None


def _port_open(port: int, timeout: float = 0.15) -> bool:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect(("127.0.0.1", port))
        s.close()
        return True
    except Exception:
        return False


def debug_port() -> int:
    return int(load_config().get("chrome_debug_port") or 9222)


def find_chrome() -> Optional[str]:
    candidates = [
        os.environ.get("CHROME_PATH"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        str(Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def _http_json(url: str, method: str = "GET", timeout: float = 1.0) -> Any:
    req = urllib.request.Request(url, method=method, data=b"" if method == "PUT" else None)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return raw


def cdp_version(port: Optional[int] = None) -> Optional[dict]:
    port = port or debug_port()
    if not _port_open(port):
        return None
    try:
        data = _http_json(f"http://127.0.0.1:{port}/json/version", timeout=0.8)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def cdp_ws_ok(port: Optional[int] = None) -> bool:
    """True if WebSocket CDP handshake works (needs --remote-allow-origins)."""
    port = port or debug_port()
    try:
        tabs = _http_json(f"http://127.0.0.1:{port}/json/list", timeout=1.0)
        if not isinstance(tabs, list):
            return False
        ws = next((t.get("webSocketDebuggerUrl") for t in tabs if t.get("webSocketDebuggerUrl")), None)
        if not ws:
            ver = cdp_version(port) or {}
            ws = ver.get("webSocketDebuggerUrl")
        if not ws:
            return False
        from websocket import create_connection

        c = create_connection(ws, timeout=2)
        c.close()
        return True
    except Exception:
        return False


def open_url_fast(url: str, port: Optional[int] = None) -> bool:
    """
    Открыть URL в уже запущенном Chrome Radar максимально быстро.
    Один короткий PUT /json/new (современный Chrome), без серии долгих таймаутов.
    """
    port = port or debug_port()
    if not _port_open(port, timeout=0.05):
        return False

    encoded = urllib.parse.quote(url, safe="")
    # Chrome ожидает PUT + URL-encoded. Короткие таймауты: лучше сразу fallback.
    attempts = (
        (f"http://127.0.0.1:{port}/json/new?{encoded}", "PUT", 0.35),
        (f"http://127.0.0.1:{port}/json/new?{encoded}", "GET", 0.25),
    )
    for endpoint, method, timeout in attempts:
        try:
            data = _http_json(endpoint, method=method, timeout=timeout)
            if data is not None:
                _bring_chrome_forward()
                return True
        except Exception:
            continue

    chrome = find_chrome()
    if not chrome:
        return False
    try:
        subprocess.Popen(
            [
                chrome,
                f"--user-data-dir={CHROME_PROFILE}",
                f"--remote-debugging-port={port}",
                "--remote-allow-origins=*",
                "--no-first-run",
                url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _bring_chrome_forward()
        return True
    except Exception:
        return False


def _bring_chrome_forward() -> None:
    """Вытащить Chrome на передний план, НЕ сбрасывая fullscreen/maximize."""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        found = []

        @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
        def _enum(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length < 1:
                return True
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value or ""
            if "Chrome" in title or "Google Chrome" in title or "hh.ru" in title.lower():
                found.append(hwnd)
            return True

        user32.EnumWindows(_enum, 0)
        if not found:
            return
        hwnd = found[0]
        # SW_RESTORE (9) сбрасывает F11/maximize — только если окно свёрнуто в панель.
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE only when minimized
        user32.SetForegroundWindow(hwnd)
    except Exception:
        return


def check_connection_fast() -> str:
    port = debug_port()
    if not _port_open(port):
        return f"Chrome Radar не запущен (порт {port}). Нажмите «Войти в HH / Открыть Chrome»."
    ver = cdp_version(port)
    if not ver:
        return f"Порт {port} открыт, но DevTools не ответил. Подождите 1–2 сек."
    browser = ver.get("Browser") or "Chrome"
    if not cdp_ws_ok(port):
        return (
            f"Chrome виден ({browser}), но CDP WebSocket закрыт (нужен перезапуск).\n"
            "Нажмите ещё раз «Войти в HH / Открыть Chrome» — Radar перезапустит Chrome правильно."
        )
    return f"Связь OK ({browser}). Порт {port}. CDP готов."


def _kill_port_listeners(port: int) -> None:
    try:
        out = subprocess.check_output(["netstat", "-ano"], text=True, errors="ignore")
        pids = set()
        for line in out.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                if parts:
                    pids.add(parts[-1])
        for pid in pids:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        time.sleep(0.7)
    except Exception:
        pass


def relaunch_chrome_for_cdp(open_login: bool = True) -> str:
    port = debug_port()
    chrome = find_chrome()
    if not chrome:
        return "Chrome не найден."
    _kill_port_listeners(port)
    invalidate_driver()
    CHROME_PROFILE.mkdir(parents=True, exist_ok=True)
    url = HH_LOGIN if open_login else HH_HOME
    subprocess.Popen(
        [
            chrome,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={CHROME_PROFILE}",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-popup-blocking",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(35):
        if _port_open(port, timeout=0.1) and cdp_ws_ok(port):
            return (
                f"Chrome Radar перезапущен с CDP (порт {port}).\n"
                "Если вылетел логин — войдите в HH снова в этом окне."
            )
        time.sleep(0.15)
    if _port_open(port):
        return f"Chrome запущен (порт {port}). Подождите секунду и нажмите «Проверить связь»."
    return "Не удалось перезапустить Chrome. Закройте окна Chrome Radar вручную и нажмите снова."


def launch_chrome_for_login(open_login: bool = True) -> str:
    port = debug_port()
    chrome = find_chrome()
    if not chrome:
        return "Chrome не найден. Установите Google Chrome."

    CHROME_PROFILE.mkdir(parents=True, exist_ok=True)
    url = HH_LOGIN if open_login else HH_HOME

    if _port_open(port):
        if not cdp_ws_ok(port):
            return relaunch_chrome_for_cdp(open_login=open_login)
        if open_login and open_url_fast(url, port):
            return f"Chrome уже запущен (порт {port}). Открыл вкладку входа HH."
        return f"Chrome уже запущен (порт {port})."

    subprocess.Popen(
        [
            chrome,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={CHROME_PROFILE}",
            "--remote-allow-origins=*",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-popup-blocking",
            url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(25):
        if _port_open(port, timeout=0.1):
            return (
                f"Chrome запущен (профиль VacancyRadar, порт {port}).\n"
                "Войдите в hh.ru в этом окне — сессия сохранится."
            )
        time.sleep(0.1)
    return "Chrome стартует… Если окно видно — войдите в HH, затем «Проверить связь»."


def invalidate_driver() -> None:
    global _cached_driver, _cached_port
    with _driver_lock:
        _cached_driver = None
        _cached_port = None


def attach_driver():
    """Legacy Selenium attach (prefer CDP modules instead)."""
    global _cached_driver, _cached_port
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options

    port = debug_port()
    if not _port_open(port):
        invalidate_driver()
        raise RuntimeError(
            f"Chrome Radar не запущен (порт {port}). Нажмите «Войти в HH / Открыть Chrome»."
        )

    with _driver_lock:
        if _cached_driver is not None and _cached_port == port:
            try:
                _ = _cached_driver.title
                return _cached_driver
            except Exception:
                _cached_driver = None

        opts = Options()
        opts.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
        driver = webdriver.Chrome(options=opts)
        driver.set_page_load_timeout(20)
        try:
            driver.implicitly_wait(0)
        except Exception:
            pass
        _cached_driver = driver
        _cached_port = port
        return driver


def ensure_chrome(open_login: bool = False):
    port = debug_port()
    if not _port_open(port) or not cdp_ws_ok(port):
        launch_chrome_for_login(open_login=open_login or True)
        for _ in range(30):
            if _port_open(port, timeout=0.1):
                break
            time.sleep(0.1)
    return attach_driver()
