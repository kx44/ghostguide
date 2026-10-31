"""Hands for the SolidWorks checks: real mouse and keyboard, and only ever into SolidWorks. Every input first checks
that SolidWorks' process owns the front window (and for a click, the spot clicked), or stops; a click or key meant for
SolidWorks must never land in another app.
"""
from __future__ import annotations

import ctypes
import time
from typing import Optional

from engine import config
from engine.live import capture, execute, windows
from engine.live.locate import uia

SHOTS = config.CACHE / "screenshots" / "solidworks"
WINDOW = "SOLIDWORKS"
u32 = ctypes.windll.user32


class Stop(SystemExit):
    pass


def win() -> windows.Win:
    w = windows.find(WINDOW)
    if w is None:
        raise Stop("SOLIDWORKS isn't open")
    return w


def _ours(hwnd: int) -> bool:
    return execute._pid(hwnd) == execute._pid(win().hwnd)


def front() -> None:
    """SolidWorks to the front, or stop. Windows refuses SetForegroundWindow from a background process unless a key
    was just pressed, hence the Alt tap."""
    w = win()
    for _ in range(6):
        fg = u32.GetForegroundWindow()
        if fg and _ours(fg):
            return
        u32.keybd_event(0x12, 0, 0, 0)
        u32.keybd_event(0x12, 0, 2, 0)
        u32.ShowWindow(w.hwnd, 9 if w.minimized else 5)
        u32.SetForegroundWindow(w.hwnd)
        time.sleep(0.5)
    if not _ours(u32.GetForegroundWindow()):
        raise Stop("SOLIDWORKS won't come to the front; stopped so no input goes to another window")


def _guard() -> None:
    fg = u32.GetForegroundWindow()
    if not fg or not _ours(fg):
        raise Stop("SOLIDWORKS lost the front; stopped")


def click(x: int, y: int, button: str = "left", count: int = 1, settle: float = 0.5) -> None:
    _guard()
    u32.SetCursorPos(x, y)      # from there: an overlay card under the cursor takes the mouse until it leaves
    time.sleep(execute.HIT_SETTLE_S)
    if execute._pid_at((x, y)) != execute._pid(win().hwnd):
        raise Stop(f"({x}, {y}) isn't SOLIDWORKS; stopped")
    execute._click(execute.Op("click", at=(x, y), button=button, count=count))
    time.sleep(settle)


def hover(x: int, y: int, settle: float = 0.4) -> None:
    _guard()
    u32.SetCursorPos(x, y)
    time.sleep(settle)


def drag(a: tuple[int, int], b: tuple[int, int], steps: int = 12, settle: float = 0.4) -> None:
    _guard()
    u32.SetCursorPos(*a)
    time.sleep(0.15)
    u32.mouse_event(2, 0, 0, 0, 0)
    for i in range(1, steps + 1):
        u32.SetCursorPos(a[0] + (b[0] - a[0]) * i // steps, a[1] + (b[1] - a[1]) * i // steps)
        time.sleep(0.02)
    time.sleep(0.1)
    u32.mouse_event(4, 0, 0, 0, 0)
    time.sleep(settle)


def keys(*names: str, settle: float = 0.5) -> None:
    _guard()
    execute._keys(tuple(names))
    time.sleep(settle)


def text(s: str, settle: float = 0.3) -> None:
    _guard()
    execute._text(s)
    time.sleep(settle)


def shot(name: str) -> Optional[object]:
    """SolidWorks with its dialogs and menus, saved for looking at later."""
    SHOTS.mkdir(parents=True, exist_ok=True)
    got = capture.with_popups(win().hwnd)
    if got is None:
        return None
    got[0].save(SHOTS / f"{name}.png")
    return got


def dump() -> list[dict]:
    return uia.dump(WINDOW, every=True)


def named(els: list[dict], types=("Button", "SplitButton", "MenuItem", "TabItem", "Edit", "CheckBox", "RadioButton", "ComboBox",
                                  "ListItem", "Window", "TreeItem", "Spinner", "Text")) -> list[str]:
    return [f"{e['type']} {e.get('name')!r} {e['rect']}" + (f" value={e['value']!r}" if e.get("value") else "")
            for e in els if e["type"] in types and e["rect"][2] > 0]
