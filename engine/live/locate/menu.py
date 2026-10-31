"""Finder stage 4d: when nothing on screen matches, the route to the control: the step's own `menu_path`, else
the app map's (docs facts), plus its shortcut. The card carries the route as path chips, so you can still get
there. Muse Wonder with a fresh screenshot is the last resort for a route nobody knows: the expensive model, so
it's asked at most once per step, and what it answers goes to the local app map for review.

Multi-hop routes are followed hop by hop (`hop_label`, `Hops`): the outline sits on the next chip's control, and a
click on it ticks that chip.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from engine import config
from engine.schema.messages import Box
from engine.schema.tutorial import Step

WONDER_MAX_TOKENS = 2048
WONDER_EFFORT = "low"
WONDER_W = 2048
WONDER_KINDS = ("button", "menu_item", "field", "tab")
WONDER_PROMPT = ("This is a screenshot of {app} ({version}). A tutorial written for an older version asks for this "
                 "control, and it can't be found on the screen by name.\nStep: {title}\nControl: {label} ({kind})\n"
                 "The tutorial says: {where}\nIf you can see the control, or what replaced it in this version, call "
                 "point_at with its box in screenshot pixels ({w} × {h}). Otherwise call menu_path with the route to "
                 "it in this version, top level first (a ribbon tab name, or a menu in the menu bar). If you don't "
                 "know, call not_found. Don't guess a route that doesn't exist.")


def route(step: Step, store=None) -> Optional[dict]:
    """{"path": [...], "shortcut": "…"} or None when no route is known."""
    path = step.target.menu_path
    shortcut = step.target.shortcut
    if store is not None:
        c = store.get(step.target.label)
        if c is not None:
            path = path or c.menu_path
            shortcut = shortcut or c.shortcut
    if not path and not shortcut:
        return None
    out: dict = {}
    if path:
        out["path"] = list(path)
    if shortcut:
        out["shortcut"] = shortcut
    return out


def tab_route(step: Step) -> Optional[list[str]]:
    """A ribbon control on a named tab ("Features tab, CommandManager") that isn't showing: that tab, then it."""
    m = re.match(r"\s*([\w ]+?) tab\b", step.target.where or "", re.I)
    return [m.group(1).strip(), step.target.label] if m else None


def describe(r: dict) -> str:
    bits = []
    if r.get("path"):
        bits.append(" › ".join(r["path"]))
    if r.get("shortcut"):
        bits.append(f"or {r['shortcut']}")
    return "Not on screen. Route: " + " ".join(bits)


def hop_label(chip: str) -> str:
    """A chip as the control's name: "Line ▾" → "Line"."""
    return re.sub(r"[\s▾▼›»]+$", "", chip).strip()


class Hops:
    """Which chip of a route you're on, per step: a click inside the current chip's box moves to the next one."""

    def __init__(self, clicked: Optional[Callable[[Box, float], bool]] = None, clock=None):
        import time
        self.clicked = clicked           # (box, since) → did you click in it since then?
        self.clock = clock or time.monotonic
        self._at: dict[int, int] = {}
        self._box: dict[int, Optional[Box]] = {}
        self._t: dict[int, float] = {}

    def current(self, n: int, path: list[str]) -> int:
        i = self._at.get(n, 0)
        box = self._box.get(n)
        if box is not None and i < len(path) - 1 and self.clicked is not None and self.clicked(box, self._t.get(n, 0.0)):
            i += 1
            self._at[n] = i
            self._box[n] = None
        return i

    def found(self, n: int, box: Optional[Box]) -> None:
        if self._box.get(n) is None and box is not None:
            self._t[n] = self.clock()
        self._box[n] = box

    def back_to_start(self, n: int) -> None:
        """The next chip's control isn't there: the menu closed again."""
        self._at[n] = 0
        self._box[n] = None

    def forget(self, n: int) -> None:
        self._at.pop(n, None)
        self._box.pop(n, None)
        self._t.pop(n, None)


class Wonder:
    """Muse Wonder as the last stage: a box or a route, for a control everything before it missed."""

    def __init__(self, app: str, version: str = "", client=None, grab=None, store=None):
        self.app, self.version = app, version
        self.client = client
        self.grab = grab             # () → (PIL image, screen origin, display scale)
        self.store = store
        self.last_how = ""
        self.asked: dict[int, tuple[Optional[Box], Optional[dict], str]] = {}

    def wanted(self, step: Step) -> bool:
        return step.target.kind in WONDER_KINDS

    def ask(self, step: Step) -> tuple[Optional[Box], Optional[dict]]:
        if step.n in self.asked:
            box, r, self.last_how = self.asked[step.n]
            return box, r
        box, r = self._ask(step)
        self.asked[step.n] = (box, r, self.last_how)
        return box, r

    def _ask(self, step: Step) -> tuple[Optional[Box], Optional[dict]]:
        from engine.live.capture import for_model
        from engine.live.locate.vision import to_screen
        from engine.models.client import ModelClient, image_part, text_part
        from engine.models.tools import MENU_PATH, NOT_FOUND, POINT_AT, MenuPath, PointAt

        shot = self.grab() if self.grab else None
        if shot is None:
            self.last_how = "wonder: no screenshot"
            return None, None
        img, origin, _ = shot
        png, scale = for_model(img, WONDER_W)
        t = step.target
        text = WONDER_PROMPT.format(app=self.app, version=self.version or "this version", title=step.title, label=t.label,
                                    kind=t.kind, where=t.where or "-", w=round(img.width * scale), h=round(img.height * scale))
        try:
            c = self.client or ModelClient()
            reply = c.chat(model=config.WONDER, max_tokens=WONDER_MAX_TOKENS, reasoning_effort=WONDER_EFFORT,
                           tools=[POINT_AT, MENU_PATH, NOT_FOUND], tag=f"wonder-step-{step.n}",
                           messages=[{"role": "user", "content": [text_part(text), image_part(png)]}])
        except Exception as e:      # budget cap, network, replay miss: a miss, never a crash
            self.last_how = f"wonder: {e}"[:120]
            return None, None
        for call in reply.tool_calls:
            if isinstance(call, PointAt):
                self.last_how = f"wonder: found it on screen ({call.confidence})"
                return to_screen(call, scale, origin), None
            if isinstance(call, MenuPath) and call.path:
                r = {"path": list(call.path), "by": "wonder"}
                self.last_how = "wonder: gave the route " + " › ".join(call.path)
                if self.store is not None:
                    self.store.add_facts(t.label, menu_path=list(call.path), source="Muse Wonder, unreviewed")
                return None, r
        self.last_how = "wonder: doesn't know it"
        return None, None
