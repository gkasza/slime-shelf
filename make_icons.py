"""Generate app icons: a friendly slime blob."""
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "public", "icons")
os.makedirs(OUT, exist_ok=True)


def make(size, path):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size, size], radius=int(size * 0.22), fill=(15, 47, 29, 255))

    pad = size * 0.18
    body = [pad, size * 0.34, size - pad, size - pad * 0.72]
    d.ellipse(body, fill=(63, 174, 90, 255))
    # highlight
    d.ellipse(
        [size * 0.34, size * 0.40, size * 0.50, size * 0.52],
        fill=(178, 235, 170, 210),
    )
    # eyes
    ey = size * 0.60
    r = size * 0.045
    for cx in (size * 0.42, size * 0.58):
        d.ellipse([cx - r, ey - r, cx + r, ey + r], fill=(18, 40, 24, 255))
    # smile
    d.arc(
        [size * 0.42, ey + size * 0.015, size * 0.58, ey + size * 0.13],
        start=200, end=340, fill=(18, 40, 24, 255), width=max(2, int(size * 0.018)),
    )
    img.save(path, "PNG")


make(192, os.path.join(OUT, "icon-192.png"))
make(512, os.path.join(OUT, "icon-512.png"))
print("icons written")
