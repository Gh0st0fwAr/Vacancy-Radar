# -*- coding: utf-8 -*-
"""Wrap footer stats into .statusbar-stats for all prototype pages."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "prototypes" / "ref04"


def wrap_footer(html: str) -> str:
    marker = '<footer class="statusbar">'
    if marker not in html:
        return html
    if 'statusbar-stats' in html:
        return html
    start = html.find(marker) + len(marker)
    updated = html.find('<div class="updated"', start)
    if updated < 0:
        return html
    before = html[start:updated]
    # insert wrapper around stats (everything before .updated)
    return (
        html[:start]
        + '\n      <div class="statusbar-stats">'
        + before.rstrip()
        + '\n      </div>\n      '
        + html[updated:]
    )


for name in ("queue.html", "stats.html", "settings.html"):
    p = ROOT / name
    raw = p.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("cp1251")
    new = wrap_footer(text)
    p.write_text(new, encoding="utf-8")
    print(name, "ok" if "statusbar-stats" in new else "SKIP")
