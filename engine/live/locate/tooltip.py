"""What a control says it is when the mouse rests on it. SolidWorks' ribbon is invisible to UI Automation, but the tooltip
it shows isn't: its first line is the command's name, for an icon with no text too. So a box found by sight can be checked
for free, and a box that's right can be remembered at once. The engine never moves the mouse for this: it reads the tooltip
when you happen to be on the box.

The name rules are pure, so they're tested off Windows.
"""
from __future__ import annotations

import re
import threading
import time
from typing import Callable, Optional

TOOLTIP_CLASSES = ("swBalloonTip", "tooltips_class32")
NO_TIP_S = 3.0        # a real button has shown its tooltip by now (it takes about a second)
TIP_REST_S = 0.6      # a tooltip read sooner than this after the mouse arrived belongs to where it was before
WATCH_EVERY_S = 0.4
SAME_SPOT_PX = 2


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


class Watch:
    """Where the mouse rests and what shows there. The finder looks only every few seconds and a tooltip can come and go
    between looks, so this samples, and what it saw holds until the mouse moves. It's also how a box on empty space gives
    itself away: the mouse has rested on it and nothing has shown."""

    def __init__(self, read_tip: Callable[[], Optional[tuple[str, tuple[int, int]]]], cursor: Callable[[], tuple[int, int]],
                 in_front: Callable[[], bool], clock: Callable[[], float] = time.monotonic):
        self.read_tip, self.cursor, self.in_front, self.clock = read_tip, cursor, in_front, clock
        self.spot: Optional[tuple[int, int]] = None
        self.since: Optional[float] = None      # None: the app wasn't in front, so its tooltips couldn't show
        self.seen: Optional[str] = None

    def note(self) -> None:
        at = self.cursor()
        if self.spot is None or max(abs(at[0] - self.spot[0]), abs(at[1] - self.spot[1])) > SAME_SPOT_PX:
            self.spot, self.since, self.seen = at, self.clock(), None
        if not self.in_front():
            self.since = None
            return
        if self.since is None:
            self.since = self.clock()
        if self.clock() - self.since < TIP_REST_S:
            return      # the tooltip up right now is still the last spot's: it would put another control's name on this one
        got = self.read_tip()
        if got:
            self.seen = got[0]

    def tip(self) -> Optional[tuple[str, tuple[int, int]]]:
        """What the tooltip says, or said, at the spot the mouse is on."""
        return (self.seen, self.spot) if self.seen and self.spot else None

    def rested(self) -> Optional[tuple[int, int]]:
        """The spot, once the mouse has stayed there long enough for a tooltip and none has shown."""
        if self.spot is None or self.since is None or self.seen or self.clock() - self.since < NO_TIP_S:
            return None
        return self.spot

    def start(self) -> "Watch":
        def run():
            while True:
                try:
                    self.note()
                except Exception:      # windows come and go; the next look will do
                    pass
                time.sleep(WATCH_EVERY_S)
        threading.Thread(target=run, daemon=True, name="tooltip-watch").start()
        return self


def watch(window: str) -> Watch:
    """A running Watch on that app's window."""
    import ctypes
    from ctypes import wintypes

    from engine.live import windows

    u32 = ctypes.windll.user32

    def cursor():
        at = wintypes.POINT()
        u32.GetCursorPos(ctypes.byref(at))
        return at.x, at.y

    def in_front():
        w = windows.foreground()
        return bool(w and window.casefold() in w.title.casefold())

    return Watch(lambda: read(window), cursor, in_front).start()


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
