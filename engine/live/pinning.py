"""`python -m engine pin <tutorial.md>`: make dev pins by hovering each target (Windows).

For each step it names the target; you hover its top-left corner and press Enter, then its
bottom-right corner and Enter (start and end point for lines). Then you do the step in the app,
since the next target often only appears after it (the filename box after New File).
Pins are saved after every step, so you can stop with q and continue later with --from.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from engine.basefile.parse import parse_file
from engine.live.locate.pinned import Pin, Pins, default_path

# Steps that have no on-screen target by default (Enter skips them; p pins anyway).
NO_TARGET = {"shortcut", "wait", "look"}


def cursor_pos() -> tuple[int, int]:
    import ctypes
    from ctypes import wintypes

    pt = wintypes.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def screen_size() -> dict:
    import ctypes

    m = ctypes.windll.user32.GetSystemMetrics
    return {"w": m(0), "h": m(1), "virtual": [m(76), m(77), m(78), m(79)]}


def box_from(p1: tuple[int, int], p2: tuple[int, int]) -> Optional[tuple[int, int, int, int]]:
    x0, y0 = min(p1[0], p2[0]), min(p1[1], p2[1])
    w, h = abs(p2[0] - p1[0]), abs(p2[1] - p1[1])
    if w < 2 or h < 2:
        return None
    return x0, y0, w, h


def _ask(prompt: str) -> str:
    try:
        return input(prompt).strip().lower()
    except EOFError:
        return "q"


def pin_interactive(tutorial: str, pins_path: Optional[str], start: int = 1, end: Optional[int] = None) -> int:
    if sys.platform != "win32":
        print("pinning reads the mouse position, so it only runs on Windows", file=sys.stderr)
        return 2
    from engine.dpi import make_dpi_aware

    make_dpi_aware()
    tut = parse_file(tutorial)
    path = Path(pins_path) if pins_path else default_path(tutorial)
    pins = Pins.load(path)
    pins.tutorial = Path(tutorial).name
    pins.screen = screen_size()
    end = end or len(tut.steps)
    by_label: dict[str, int] = {}
    for n, p in pins.steps.items():
        by_label.setdefault(tut.step(n).target.label.lower(), n)

    print(f"Pinning {tut.meta.title}, steps {start}–{end} → {path}")
    print("Keep this terminal focused; only move the mouse over the app. Keys at each prompt:")
    print("  Enter = take the point under the mouse · s = skip step · r = reuse the last pin with the same label")
    print("  k = keep the existing pin · q = save and quit\n")
    for step in tut.steps[start - 1:end]:
        n, label = step.n, step.target.label
        line_step = step.action in ("draw_line", "drag")
        print(f"Step {n} — {step.title}  [{step.action}]")
        print(f"  target: {label} ({step.target.kind})" + (f", {step.target.where}" if step.target.where else ""))
        same = by_label.get(label.lower())
        if n in pins.steps:
            print(f"  already pinned: {pins.steps[n].model_dump(exclude_none=True)}")
        if step.action in NO_TARGET and n not in pins.steps:
            a = _ask("  no on-screen target needed. Enter = skip, p = pin a button equivalent anyway, q = quit: ")
            if a == "q":
                break
            if a != "p":
                if _do_step(step):
                    break
                continue
        first = "start point" if line_step else "TOP-LEFT corner"
        second = "end point" if line_step else "BOTTOM-RIGHT corner"
        a = _ask(f"  hover the {first}, press Enter" + (f" (r = same as step {same})" if same and same != n else "") + ": ")
        if a == "q":
            break
        if a == "s" or (a == "k" and n in pins.steps):
            if _do_step(step):
                break
            continue
        if a == "r" and same and same != n:
            pins.steps[n] = Pin(same_as=same)
        else:
            p1 = cursor_pos()
            a = _ask(f"    {p1} · now the {second}, Enter: ")
            if a == "q":
                break
            p2 = cursor_pos()
            if line_step:
                pins.steps[n] = Pin(line=(p1, p2))
            else:
                b = box_from(p1, p2)
                if b is None:
                    print("    too small (move between the two corners); skipped. Re-run with --from", n)
                    continue
                pins.steps[n] = Pin(box=b)
            print(f"    pinned {pins.steps[n].model_dump(exclude_none=True)}")
            by_label.setdefault(label.lower(), n)
        pins.dump(path)
        if _do_step(step):
            break
    pins.dump(path)
    print(f"\nsaved {len(pins.steps)} pins → {path}")
    return 0


def _do_step(step) -> bool:
    """True if you typed q (quit)."""
    return _ask("  now do this step in the app (so the next target appears), then press Enter: ") == "q"
