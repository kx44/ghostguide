"""Draws the tray icons (tray.ico, tray-paused.ico): a small ghost, violet while guiding and grey while paused.

    py overlay/assets/make_icons.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).parent
SIZES = [16, 20, 24, 32, 40, 48, 64, 256]
SS = 8      # drawn large, then scaled down, so the edges stay smooth


def ghost(size: int, body: str) -> Image.Image:
    s = size * SS
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    m = s * 0.08
    left, right, top, bottom = m, s - m, m * 0.6, s - m * 0.4
    w = right - left
    d.ellipse([left, top, right, top + w], fill=body)      # the head
    d.rectangle([left, top + w / 2, right, bottom - w / 6], fill=body)
    for i in range(3):                                     # the hem
        x0 = left + i * w / 3
        d.ellipse([x0, bottom - w / 3, x0 + w / 3, bottom], fill=body)
    eye = w * 0.17
    for cx in (left + w * 0.33, left + w * 0.67):
        d.ellipse([cx - eye / 2, top + w * 0.3, cx + eye / 2, top + w * 0.3 + eye * 1.25], fill="#FFFFFF")
    return im.resize((size, size), Image.LANCZOS)


def write(name: str, body: str) -> None:
    images = [ghost(s, body) for s in SIZES]
    images[-1].save(HERE / name, format="ICO", sizes=[(s, s) for s in SIZES], append_images=images[:-1])


write("tray.ico", "#7C3AED")
write("tray-paused.ico", "#7B7788")
