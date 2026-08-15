# -*- coding: utf-8 -*-
"""Generate transparent teal line icons for VacancyRadar toolbar."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
TEAL = (79, 209, 197, 255)  # #4fd1c5
WHITE = (232, 237, 242, 255)
MUTED = (168, 179, 192, 255)


def blank(size=64):
    return Image.new("RGBA", (size, size), (0, 0, 0, 0))


def save(im: Image.Image, name: str):
    path = OUT / name
    im.save(path)
    print("wrote", path, path.stat().st_size)


def icon_search():
    im = blank()
    d = ImageDraw.Draw(im)
    d.ellipse((14, 14, 40, 40), outline=TEAL, width=3)
    d.line((38, 38, 50, 50), fill=TEAL, width=3)
    save(im, "tb_search.png")


def icon_refresh():
    im = blank()
    d = ImageDraw.Draw(im)
    d.arc((12, 12, 52, 52), 40, 300, fill=TEAL, width=3)
    d.polygon([(48, 18), (54, 30), (42, 28)], fill=TEAL)
    save(im, "tb_refresh.png")


def icon_queue():
    im = blank()
    d = ImageDraw.Draw(im)
    for y in (18, 30, 42):
        d.rounded_rectangle((14, y, 50, y + 8), radius=3, outline=TEAL, width=2)
    save(im, "tb_queue.png")


def icon_stats():
    im = blank()
    d = ImageDraw.Draw(im)
    d.rectangle((14, 36, 22, 50), fill=TEAL)
    d.rectangle((28, 24, 36, 50), fill=TEAL)
    d.rectangle((42, 14, 50, 50), fill=TEAL)
    save(im, "tb_stats.png")


def icon_settings():
    im = blank()
    d = ImageDraw.Draw(im)
    cx, cy, r = 32, 32, 10
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=TEAL, width=3)
    for ang in range(0, 360, 45):
        import math

        a = math.radians(ang)
        x1 = cx + int(16 * math.cos(a))
        y1 = cy + int(16 * math.sin(a))
        x2 = cx + int(24 * math.cos(a))
        y2 = cy + int(24 * math.sin(a))
        d.line((x1, y1, x2, y2), fill=TEAL, width=3)
    save(im, "tb_settings.png")


def icon_external():
    im = blank(48)
    d = ImageDraw.Draw(im)
    d.rectangle((10, 14, 30, 34), outline=TEAL, width=2)
    d.line((26, 12, 38, 12), fill=TEAL, width=2)
    d.line((38, 12, 38, 24), fill=TEAL, width=2)
    d.line((22, 26, 38, 12), fill=TEAL, width=2)
    save(im, "tb_external.png")


def icon_copy():
    im = blank(48)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((12, 16, 30, 38), radius=3, outline=TEAL, width=2)
    d.rounded_rectangle((18, 10, 36, 32), radius=3, outline=TEAL, width=2)
    save(im, "tb_copy.png")


def icon_briefcase():
    im = blank(40)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((6, 14, 34, 34), radius=3, outline=TEAL, width=2)
    d.rectangle((16, 8, 24, 14), outline=TEAL, width=2)
    save(im, "st_total.png")


def icon_new():
    im = blank(40)
    d = ImageDraw.Draw(im)
    d.ellipse((8, 8, 32, 32), outline=TEAL, width=2)
    d.line((20, 14, 20, 26), fill=TEAL, width=2)
    d.line((14, 20, 26, 20), fill=TEAL, width=2)
    save(im, "st_new.png")


def icon_applied():
    im = blank(40)
    d = ImageDraw.Draw(im)
    d.ellipse((8, 8, 32, 32), outline=MUTED, width=2)
    d.line((14, 20, 18, 26), fill=MUTED, width=2)
    d.line((18, 26, 28, 14), fill=MUTED, width=2)
    save(im, "st_applied.png")


def icon_replies():
    im = blank(40)
    d = ImageDraw.Draw(im)
    blue = (126, 182, 240, 255)
    d.ellipse((8, 12, 22, 26), outline=blue, width=2)
    d.ellipse((18, 12, 32, 26), outline=blue, width=2)
    save(im, "st_replies.png")


def icon_interview():
    im = blank(40)
    d = ImageDraw.Draw(im)
    purp = (167, 139, 250, 255)
    d.rounded_rectangle((10, 8, 30, 34), radius=2, outline=purp, width=2)
    d.line((14, 16, 26, 16), fill=purp, width=2)
    d.line((14, 22, 26, 22), fill=purp, width=2)
    save(im, "st_interview.png")


def icon_offer():
    im = blank(40)
    d = ImageDraw.Draw(im)
    gold = (230, 195, 92, 255)
    d.rectangle((10, 16, 30, 34), outline=gold, width=2)
    d.line((20, 10, 20, 16), fill=gold, width=2)
    d.arc((12, 8, 28, 20), 0, 180, fill=gold, width=2)
    save(im, "st_offer.png")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    icon_search()
    icon_refresh()
    icon_queue()
    icon_stats()
    icon_settings()
    icon_external()
    icon_copy()
    icon_briefcase()
    icon_new()
    icon_applied()
    icon_replies()
    icon_interview()
    icon_offer()
    print("done")
