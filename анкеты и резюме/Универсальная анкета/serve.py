# -*- coding: utf-8 -*-
"""Local saver for the universal questionnaire. Stdlib only."""
from __future__ import annotations

import json
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent  # анкеты и резюме
INDEX = HERE / "index.html"
HOST = "127.0.0.1"
PORT = 8765


def safe_folder_name(name: str) -> str:
    text = (name or "").strip()
    text = re.sub(r'[\\/:*?"<>|]+', "_", text)
    text = re.sub(r"\s+", " ", text).strip(" ._")
    return text[:80] or "Без_имени"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = unquote(urlparse(self.path).path)
        if path in ("/", "/index.html"):
            data = INDEX.read_bytes()
            self._send(200, data, "text/html; charset=utf-8")
            return
        self._send(404, "Not found".encode("utf-8"), "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/save":
            self._send(404, b"Not found", "text/plain; charset=utf-8")
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception:
            self._send(400, json.dumps({"ok": False, "error": "JSON"}).encode("utf-8"), "application/json")
            return
        name = safe_folder_name(str(payload.get("name") or ""))
        text = str(payload.get("text") or "").strip()
        snippet = payload.get("config") or {}
        if not text:
            self._send(
                400,
                json.dumps({"ok": False, "error": "Пустая анкета"}).encode("utf-8"),
                "application/json; charset=utf-8",
            )
            return
        folder = PARENT / f"Анкета_{name}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "анкета.txt").write_text(text + "\n", encoding="utf-8")
        (folder / "config_snippet.json").write_text(
            json.dumps(snippet, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        note = folder / "ПОЛОЖИТЕ_РЕЗЮМЕ_СЮДА.txt"
        if not note.exists():
            note.write_text(
                "Положите в эту папку PDF (или TXT) резюме.\n"
                "Имя файла любое: например resume.pdf или nstyacv.pdf.\n"
                "Путь потом пропишем в VacancyRadar data/config.json → resume_path.\n",
                encoding="utf-8",
            )
        rel = folder.relative_to(PARENT.parent).as_posix()
        body = json.dumps(
            {
                "ok": True,
                "folder": str(folder),
                "relative": rel,
                "txt": str(folder / "анкета.txt"),
            },
            ensure_ascii=False,
        ).encode("utf-8")
        self._send(200, body, "application/json; charset=utf-8")


def main() -> int:
    if not INDEX.exists():
        print("Нет index.html рядом с serve.py", file=sys.stderr)
        return 1
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Анкета: http://{HOST}:{PORT}/")
    print("Сохранение в папку на уровень выше: анкеты и резюме/Анкета_Имя/")
    print("Остановка: Ctrl+C")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nСервер остановлен.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
