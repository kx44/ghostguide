"""What a control says it is when the mouse rests on it. SolidWorks' ribbon is invisible to UI Automation, but the tooltip
it shows isn't: its first line is the command's name, for an icon with no text too. So a box found by sight can be checked
for free, and a box that's right can be remembered at once. The engine never moves the mouse for this: it reads the tooltip
when you happen to be on the box.

The name rules are pure, so they're tested off Windows.
"""
from __future__ import annotations

import re
from typing import Optional

TOOLTIP_CLASSES = ("swBalloonTip", "tooltips_class32")


def clean(text: str) -> str:
    """"Line   (L)" → "Line": the shortcut in brackets isn't part of the name."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", (text or "").strip())


def _words(text: str) -> list[str]:
    return re.findall(r"[\w/]+", clean(text).casefold())


def same_control(want: str, shown: str) -> bool:
    """The tooltip names this control. It may say more in front: "Straight Slot" shows as "Centerpoint Straight Slot", the
    one it last opened, and "Sketch" as "Exit Sketch" while sketching. "Sketch Fillet" isn't "Sketch"."""
    a, b = _words(want), _words(shown)
    return bool(a) and b[-len(a):] == a


def first_line(texts: list[Optional[str]]) -> Optional[str]:
    return next((clean(t) for t in texts if t and clean(t)), None)


def read(window: str) -> Optional[tuple[str, tuple[int, int]]]:
    """(the tooltip's name, where the mouse is), when the app is showing a tooltip right now. A UIA look at one small window."""
    import ctypes
    from ctypes import wintypes

    import uiautomation as auto

    from engine.live import windows
    from engine.live.execute import _pid

    w = windows.find(window)
    if w is None:
        return None
    pid = _pid(w.hwnd)
    u32 = ctypes.windll.user32
    tips: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(h, _):
        name = ctypes.create_unicode_buffer(64)
        u32.GetClassNameW(h, name, 64)
        if name.value in TOOLTIP_CLASSES and u32.IsWindowVisible(h) and _pid(h) == pid:
            tips.append(h)
        return True

    u32.EnumWindows(each, 0)
    for h in tips:
        try:
            top = auto.ControlFromHandle(h)
            name = first_line([c.Name for c in top.GetChildren() if c.ControlTypeName == "TextControl"] + [top.Name])
        except Exception:      # a tooltip can go between looking and reading
            continue
        if name:
            at = wintypes.POINT()
            u32.GetCursorPos(ctypes.byref(at))
            return name, (at.x, at.y)
    return None
