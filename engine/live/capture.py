"""Screen capture (live step 3) and the free pixel diff (live step 9b).

A window is captured with PrintWindow(PW_RENDERFULLCONTENT): the app draws itself into our bitmap, so our own
overlay is never in the picture and nothing has to be hidden (hiding the overlay for a frame on every check
would flicker). Chromium apps (VS Code, Chrome) render fine this way. A screen region falls back to a plain
screen grab, which does include the overlay; the caller clears it first if that matters.

The diff is pure (Pillow only): both images shrunk to a small grey thumbnail, then the share of cells that
changed by more than a threshold. Shrinking first makes it cheap and ignores a blinking caret or anti-aliasing.
"""
from __future__ import annotations

import sys
from typing import Optional

GAP_PX = 2       # snug: an icon's parts are this close
DIFF_W = 160            # thumbnail width for diffs
CELL_DELTA = 18         # grey levels a thumbnail pixel must move to count as changed
CHANGED_SHARE = 0.004   # this share of changed cells = "the screen changed" (~100 of 25,000)
MODEL_W = 1280          # width of the copy sent to a model


def thumb(img, width: int = DIFF_W):
    w, h = img.size
    if w <= 0 or h <= 0:
        return img.convert("L")
    return img.convert("L").resize((width, max(1, round(h * width / w))))


def changed_share(a, b, delta: int = CELL_DELTA, width: int = DIFF_W) -> float:
    """Share of thumbnail cells that differ by more than `delta` (0..1). Different sizes = everything changed."""
    ta, tb = thumb(a, width), thumb(b, width)
    if ta.size != tb.size:
        return 1.0
    pa, pb = ta.tobytes(), tb.tobytes()
    n = len(pa)
    return sum(1 for x, y in zip(pa, pb) if abs(x - y) > delta) / n if n else 0.0


def changed(a, b, share: float = CHANGED_SHARE, width: int = DIFF_W) -> bool:
    return changed_share(a, b, width=width) > share


ARROW_LEFT, ARROW_RIGHT, ARROW_UP, ARROW_DOWN = 10, 26, 24, 8   # where to search, px around the button's box
ARROW_DARK = 90
BIG_BUTTON_H = 60
ARROW_MIN_W, ARROW_MAX_W = 6, 14
LOOK_SIDE = 16          # a control's remembered look: this many grey cells a side
LOOK_DELTA = 6          # mean grey levels two looks may differ by, once an even shift is taken out, and still be the same
                        # control. A hover shade shifts every cell alike. A neighbour on another ribbon tab doesn't: measured
                        # on real pairs, the same control differs by 0 and a different one by 10 or more


def look_of(img) -> list[int]:
    return list(img.convert("L").resize((LOOK_SIDE, LOOK_SIDE)).tobytes())


def dropdown_arrow(img, box: tuple[int, int, int, int], origin: tuple[int, int] = (0, 0)) -> Optional[tuple[int, int]]:
    """The small black triangle of a dropdown just right of a ribbon button, to the pixel (screen coordinates), or None.
    A row of dark pixels, each row below it narrower. Model boxes are too loose for a target this small, and it's free."""
    x, y, w, h = box[0] - origin[0], box[1] - origin[1], box[2], box[3]
    x0, x1 = max(0, x + w - ARROW_LEFT), min(img.width, x + w + ARROW_RIGHT)
    y0, y1 = max(0, y - ARROW_UP), min(img.height, y + h + ARROW_DOWN)
    if h >= BIG_BUTTON_H:                 # a big ribbon button: its arrow is under its own label, not beside it
        x0, x1 = max(0, x), min(img.width, x + w)
        y0, y1 = max(0, y + h // 2), min(img.height, y + h + ARROW_DOWN)
    if x1 <= x0 or y1 <= y0:
        return None
    grey = img.convert("L").crop((x0, y0, x1, y1))
    px, W, H = grey.load(), grey.width, grey.height

    def runs(r: int) -> list[tuple[int, int]]:
        out, s = [], None
        for c in range(W + 1):
            dark = c < W and px[c, r] < ARROW_DARK
            if dark and s is None:
                s = c
            elif not dark and s is not None:
                out.append((s, c - s))
                s = None
        return out

    best = None
    for r in range(H - 3):
        for s, n in runs(r):
            if not ARROW_MIN_W <= n <= ARROW_MAX_W:
                continue
            mid = s + n / 2
            below = [m for m in runs(r + 2) if abs(m[0] + m[1] / 2 - mid) <= 1.5]
            if below and below[0][1] < n and not [a for a in runs(max(0, r - 1)) if abs(a[0] + a[1] / 2 - mid) <= 3 and r > 0]:
                sy = y0 + r + 2
                d = abs(sy - (y + h / 2))
                if best is None or d < best[0]:
                    best = (d, x0 + round(mid), sy)
    return (best[1] + origin[0], best[2] + origin[1]) if best else None


def snug(img, box: tuple[int, int, int, int], origin: tuple[int, int] = (0, 0), pad: int = 2, ink: int = 28) -> tuple[int, int, int, int]:
    """A loose box moved onto what it's loosely on: looks a little around it for the thing that overlaps it most, and takes
    that thing's edges. Model boxes name the right control and can sit half off it, which is also where a click would land.
    Keeps the box when nothing there looks like one control: a line across the window, or a thing much bigger than the box."""
    x, y, w, h = box[0] - origin[0], box[1] - origin[1], box[2], box[3]
    around = max(10, min(w, h) // 2)
    x0, y0, x1, y1 = max(0, x - around), max(0, y - around), min(img.width, x + w + around), min(img.height, y + h + around)
    if x1 - x0 < 6 or y1 - y0 < 6:
        return box
    part = img.crop((x0, y0, x1, y1)).convert("L")
    px, W, H = part.load(), part.width, part.height
    bg = sorted(part.getdata())[W * H // 2]
    ink_at = [[abs(px[i, j] - bg) > ink for i in range(W)] for j in range(H)]
    seen: set[tuple[int, int]] = set()
    best, best_overlap = None, 0
    for j0 in range(H):
        for i0 in range(W):
            if not ink_at[j0][i0] or (i0, j0) in seen:
                continue
            todo, l, t, r, b, overlap = [(i0, j0)], i0, j0, i0, j0, 0
            seen.add((i0, j0))
            while todo:
                i, j = todo.pop()
                l, t, r, b = min(l, i), min(t, j), max(r, i), max(b, j)
                overlap += x <= x0 + i < x + w and y <= y0 + j < y + h
                for di in range(-GAP_PX, GAP_PX + 1):         # an icon's parts are close together, not always touching
                    for dj in range(-GAP_PX, GAP_PX + 1):
                        n = (i + di, j + dj)
                        if 0 <= n[0] < W and 0 <= n[1] < H and ink_at[n[1]][n[0]] and n not in seen:
                            seen.add(n)
                            todo.append(n)
            if overlap > best_overlap and r - l + 1 <= w * 2 and b - t + 1 <= h * 2 and l > 0 and t > 0 and r < W - 1 and b < H - 1:
                best, best_overlap = (l, t, r, b), overlap
    if best is None or best[2] - best[0] < 5 or best[3] - best[1] < 5:
        return box
    l, t, r, b = best
    if not (x <= x0 + (l + r) / 2 <= x + w and y <= y0 + (t + b) / 2 <= y + h):
        return box                            # mostly outside it: that's the control next door
    return x0 + l - pad + origin[0], y0 + t - pad + origin[1], r - l + 1 + 2 * pad, b - t + 1 + 2 * pad


def near_clicks(img, clicks: list[tuple[int, int]], origin: tuple[int, int], pad: int = 320):
    """The part of a picture around these screen points: thin sketch lines need a close look. None without clicks."""
    if not clicks:
        return None
    xs, ys = [c[0] - origin[0] for c in clicks], [c[1] - origin[1] for c in clicks]
    return img.crop((max(0, min(xs) - pad), max(0, min(ys) - pad), min(img.width, max(xs) + pad), min(img.height, max(ys) + pad)))


def same_look(a: list[int], b: list[int], delta: int = LOOK_DELTA) -> bool:
    if len(a) != len(b) or not a:
        return False
    shift = sum(x - y for x, y in zip(a, b)) / len(a)
    return sum(abs(x - y - shift) for x, y in zip(a, b)) / len(a) <= delta


def for_model(img, width: int = MODEL_W):
    """(PNG bytes, scale) of a copy at most `width` wide; screen px = model px / scale."""
    import io

    w, h = img.size
    scale = min(1.0, width / w) if w else 1.0
    small = img if scale == 1.0 else img.resize((round(w * scale), round(h * scale)))
    buf = io.BytesIO()
    small.convert("RGB").save(buf, format="PNG")
    return buf.getvalue(), scale


def crop(img, box: tuple[int, int, int, int], origin: tuple[int, int] = (0, 0), pad: int = 0):
    """Crop screen box (x, y, w, h) out of an image whose top-left is at screen `origin`."""
    x, y, w, h = box
    ox, oy = origin
    l, t = max(0, x - pad - ox), max(0, y - pad - oy)
    r, b = min(img.width, x + w + pad - ox), min(img.height, y + h + pad - oy)
    return img.crop((l, t, max(l + 1, r), max(t + 1, b)))


# ---------- Windows -------------------------------------------------------------------------------
def window(hwnd: int):
    """The window's own pixels as a PIL image (its visible frame), or None (minimised, or it won't draw)."""
    if sys.platform != "win32":
        return None
    import ctypes
    import ctypes.wintypes as wt

    from PIL import Image

    from engine.live.windows import frame

    u32, gdi = ctypes.windll.user32, ctypes.windll.gdi32
    H = ctypes.c_void_p                              # handles are 64-bit; ctypes' default int would cut them
    u32.GetWindowDC.restype = H
    u32.GetWindowDC.argtypes = [wt.HWND]
    u32.ReleaseDC.argtypes = [wt.HWND, H]
    u32.PrintWindow.argtypes = [wt.HWND, H, wt.UINT]
    gdi.CreateCompatibleDC.restype = H
    gdi.CreateCompatibleDC.argtypes = [H]
    gdi.CreateCompatibleBitmap.restype = H
    gdi.CreateCompatibleBitmap.argtypes = [H, ctypes.c_int, ctypes.c_int]
    gdi.SelectObject.restype = H
    gdi.SelectObject.argtypes = [H, H]
    gdi.DeleteObject.argtypes = [H]
    gdi.DeleteDC.argtypes = [H]
    gdi.GetDIBits.argtypes = [H, H, wt.UINT, wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.UINT]
    if u32.IsIconic(hwnd):
        return None
    wr = wt.RECT()
    u32.GetWindowRect(hwnd, ctypes.byref(wr))
    w, h = wr.right - wr.left, wr.bottom - wr.top
    if w <= 0 or h <= 0:
        return None
    hdc = u32.GetWindowDC(hwnd)
    mdc = gdi.CreateCompatibleDC(hdc)
    bmp = gdi.CreateCompatibleBitmap(hdc, w, h)
    old = gdi.SelectObject(mdc, bmp)
    try:
        ok = u32.PrintWindow(hwnd, mdc, 2)          # PW_RENDERFULLCONTENT
        if not ok:
            return None

        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                        ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                        ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                        ("biClrImportant", wt.DWORD)]

        bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        gdi.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
        img = Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB")
    finally:
        gdi.SelectObject(mdc, old)
        gdi.DeleteObject(bmp)
        gdi.DeleteDC(mdc)
        u32.ReleaseDC(hwnd, hdc)
    # GetWindowRect includes the invisible resize border; cut down to the visible frame.
    fx, fy, fw, fh = frame(hwnd)
    return img.crop((fx - wr.left, fy - wr.top, fx - wr.left + fw, fy - wr.top + fh))


def with_popups(hwnd: int):
    """The window plus its process's dialogs and open menus (their own top-level windows, which PrintWindow on the
    main window doesn't show), each from its own pixels, on one picture. → (image, screen origin), or None."""
    from PIL import Image

    from engine.live.windows import frame, same_process

    base = window(hwnd)
    if base is None:
        return None
    fx, fy, fw, fh = frame(hwnd)
    pops = [(p, window(p.hwnd)) for p in same_process(hwnd)]
    pops = [(p, im) for p, im in pops if im is not None]
    if not pops:
        return base, (fx, fy)
    x0, y0 = min([fx] + [p.rect[0] for p, _ in pops]), min([fy] + [p.rect[1] for p, _ in pops])
    x1 = max([fx + fw] + [p.rect[0] + p.rect[2] for p, _ in pops])
    y1 = max([fy + fh] + [p.rect[1] + p.rect[3] for p, _ in pops])
    out = Image.new("RGB", (x1 - x0, y1 - y0), (32, 32, 32))
    out.paste(base, (fx - x0, fy - y0))
    for p, im in pops:
        out.paste(im, (p.rect[0] - x0, p.rect[1] - y0))
    return out, (x0, y0)


def region(box: tuple[int, int, int, int]):
    """Screen pixels in box (x, y, w, h), all monitors. Includes whatever the overlay draws there."""
    from PIL import ImageGrab

    x, y, w, h = box
    return ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)


def window_region(hwnd: int, box: Optional[tuple[int, int, int, int]], pad: int = 60):
    """The part of a window around a screen box (or the whole window), from the window's own pixels."""
    from engine.live.windows import frame

    img = window(hwnd)
    if img is None or box is None:
        return img
    fx, fy, _, _ = frame(hwnd)
    return crop(img, box, (fx, fy), pad)
