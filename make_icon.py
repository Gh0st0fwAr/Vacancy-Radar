# -*- coding: utf-8 -*-
"""Create radar.ico for VacancyRadar."""
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent / "assets" / "radar.ico"
OUT.parent.mkdir(parents=True, exist_ok=True)

sizes = [16, 32, 48, 64, 128, 256]
images = []
for s in sizes:
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    # dark navy circle
    pad = max(1, s // 16)
    d.ellipse([pad, pad, s - pad - 1, s - pad - 1], fill=(15, 40, 80, 255))
    # cyan rings
    cx = cy = s / 2
    for i, ratio in enumerate((0.85, 0.62, 0.38)):
        r = s * ratio / 2
        width = max(1, s // 24)
        color = (64, 196, 180, 255) if i < 2 else (120, 230, 210, 255)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=width)
    # sweep wedge
    r = s * 0.42
    d.pieslice([cx - r, cy - r, cx + r, cy + r], start=300, end=360, fill=(80, 220, 200, 160))
    # center dot
    r2 = max(2, s // 10)
    d.ellipse([cx - r2, cy - r2, cx + r2, cy + r2], fill=(255, 220, 80, 255))
    images.append(im)

images[0].save(OUT, format="ICO", sizes=[(im.width, im.height) for im in images], append_images=images[1:])
print("Wrote", OUT)
