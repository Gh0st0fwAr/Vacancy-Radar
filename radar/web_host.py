# -*- coding: utf-8 -*-
"""QWebEngine host + JS bridge for VacancyRadar ref04 UI."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional

from PySide6.QtCore import QObject, Qt, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

WEBUI_DIR = Path(__file__).resolve().parent / "webui"


class RadarBridge(QObject):
    """Methods callable from JavaScript via QWebChannel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._handlers: dict[str, Callable] = {}

    def bind(self, name: str, fn: Callable) -> None:
        self._handlers[name] = fn

    @Slot(str, str)
    def call(self, action: str, payload_json: str = "{}") -> None:
        fn = self._handlers.get(action)
        if not fn:
            return
        try:
            payload = json.loads(payload_json or "{}")
        except Exception:
            payload = {}
        try:
            fn(payload if isinstance(payload, dict) else {})
        except Exception as e:
            err = self._handlers.get("_error")
            if err:
                err({"action": action, "error": str(e)})


class WebUiHost(QWidget):
    """Embeds ref04 HTML UI and pushes JSON state into the page."""

    ready = Signal()

    def __init__(self, parent=None, zoom: float = 1.35):
        super().__init__(parent)
        self.view = QWebEngineView(self)
        self.bridge = RadarBridge(self)
        self._ready = False
        self._pending: list[tuple[str, Any]] = []
        self._zoom = max(0.8, min(2.0, float(zoom or 1.35)))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)

        settings = self.view.settings()
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)

        # Chromium page zoom (reflows layout). CSS zoom is NOT used.
        self.view.setZoomFactor(self._zoom)

        channel = QWebChannel(self.view.page())
        channel.registerObject("radar", self.bridge)
        self.view.page().setWebChannel(channel)

        self.view.loadFinished.connect(self._on_loaded)
        index = WEBUI_DIR / "index.html"
        self.view.load(QUrl.fromLocalFile(str(index.resolve())))

    def _on_loaded(self, ok: bool) -> None:
        self._ready = bool(ok)
        if ok:
            self.view.setZoomFactor(self._zoom)
            for name, data in self._pending:
                self._emit(name, data)
            self._pending.clear()
            self.ready.emit()

    def bind(self, action: str, fn: Callable) -> None:
        self.bridge.bind(action, fn)

    def _emit(self, event: str, data: Any) -> None:
        payload = json.dumps(data, ensure_ascii=False)
        # Escape for JS string in single quotes via JSON (already quoted).
        js = f"window.RadarUI && window.RadarUI.onEvent({json.dumps(event)}, {payload});"
        self.view.page().runJavaScript(js)

    def push(self, event: str, data: Any) -> None:
        if not self._ready:
            self._pending.append((event, data))
            return
        self._emit(event, data)

    def set_busy(self, search: Optional[bool] = None, stats: Optional[bool] = None) -> None:
        payload = {}
        if search is not None:
            payload["search"] = search
        if stats is not None:
            payload["stats"] = stats
        self.push("busy", payload)
