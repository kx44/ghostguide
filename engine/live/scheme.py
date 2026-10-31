"""Light / dark scheme from the app pixels behind the target .

Average luminance in a ≈48 px ring around the target: above 0.45 → light scheme, else dark.
No screenshot → the Windows app theme. Rec. 709 weights on the 0–255 values, so the 0.45 threshold means the same thing.
"""
from __future__ import annotations

import sys
from typing import Optional

from engine import config
from engine.schema.messages import Box

# Sample every Nth pixel along each axis; the ring is large and smooth, so this costs nothing in accuracy.
STEP_PX = 4


def ring_bounds(box: Box, ring: int, width: int, height: int) -> tuple[int, int, int, int]:
    """Outer rectangle of the ring, clipped to the image: (x0, y0, x1, y1), exclusive ends."""
    return (max(0, box.x - ring), max(0, box.y - ring),
            min(width, box.x + box.w + ring), min(height, box.y + box.h + ring))


def ring_luminance(image, box: Box, ring: int = config.SCHEME_RING_PX, origin: tuple[int, int] = (0, 0)) -> Optional[float]:
    """Mean luminance 0..1 of the ring around `box` (excluding the box itself) in a PIL image.

    `origin` is the screen position of the image's top-left pixel, so a cropped grab works with
    screen-space boxes. Returns None if no ring pixel falls inside the image.
    """
    rgb = image.convert("RGB")
    w, h = rgb.size
    b = Box(x=box.x - origin[0], y=box.y - origin[1], w=box.w, h=box.h)
    x0, y0, x1, y1 = ring_bounds(b, ring, w, h)
    px = rgb.load()
    total, count = 0.0, 0
    for y in range(y0, y1, STEP_PX):
        inside_rows = b.y <= y < b.y + b.h
        for x in range(x0, x1, STEP_PX):
            if inside_rows and b.x <= x < b.x + b.w:
                continue
            r, g, bl = px[x, y]
            total += 0.2126 * r + 0.7152 * g + 0.0722 * bl
            count += 1
    if not count:
        return None
    return total / count / 255.0


def scheme_for(luminance: Optional[float], fallback: Optional[str] = None) -> str:
    if luminance is None:
        return fallback or windows_theme()
    return "light" if luminance > config.SCHEME_LIGHT_ABOVE else "dark"


def windows_theme() -> str:
    """The Windows *app* theme (not the taskbar one). Light off Windows or if unreadable."""
    if sys.platform != "win32":
        return "light"
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as k:
            value, _ = winreg.QueryValueEx(k, "AppsUseLightTheme")
        return "light" if value else "dark"
    except OSError:
        return "light"


def grab_ring(box: Box, ring: int = config.SCHEME_RING_PX):
    """Screenshot of just the ring's rectangle (physical px). Returns (image, origin) or (None, None).

    Only this small grab is needed. The caller clears the overlay first so our own outline isn't measured.
    """
    if sys.platform != "win32":
        return None, None
    try:
        from PIL import ImageGrab
    except ImportError:
        return None, None
    x0, y0 = box.x - ring, box.y - ring
    x1, y1 = box.x + box.w + ring, box.y + box.h + ring
    # Clip to the virtual desktop: Pillow pads outside it with black, which would read as "dark".
    import ctypes

    m = ctypes.windll.user32.GetSystemMetrics
    vx, vy, vw, vh = m(76), m(77), m(78), m(79)   # SM_X/YVIRTUALSCREEN, SM_CX/CYVIRTUALSCREEN
    x0, y0, x1, y1 = max(x0, vx), max(y0, vy), min(x1, vx + vw), min(y1, vy + vh)
    if x1 <= x0 or y1 <= y0:
        return None, None
    try:
        img = ImageGrab.grab(bbox=(x0, y0, x1, y1), all_screens=True)
    except OSError:
        return None, None
    return img, (x0, y0)


def pick_scheme(box: Optional[Box], override: Optional[str] = None) -> tuple[str, Optional[float]]:
    """(scheme, measured luminance or None). `override` = light | dark skips measuring."""
    if override in ("light", "dark"):
        return override, None
    if box is None:
        return windows_theme(), None
    img, origin = grab_ring(box)
    if img is None:
        return windows_theme(), None
    lum = ring_luminance(img, box, origin=origin)
    return scheme_for(lum), lum
