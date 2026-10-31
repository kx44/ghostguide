"""Choose the guidance for a step (live step 5): a fixed rule, no model, so the same step always looks
the same and costs nothing. Input: the step, where its target is (box / line, or none) and the
displays; output: the `guide` message for the overlay.

Rules (Guidance glossary + 04 Base format):
- action → style: click 1 (repeat 3) · draw_line/drag 2 (repeat 4) · type 5 (code card) · shortcut 6 · pick 7 ·
  menu_path 8 · switch_app 10 · wait 12 · look = card only.
- First time vs repeat is decided from tutorial order (`repeat_of`, or the same action on the same
  label earlier), never from what happened at runtime.
- 11 click type: the first right / double / modifier click of its kind gets the mouse icon; repeats drop it.
- 9 off-screen: the target exists but lies outside every display → edge pill on the nearest one.
- No target on screen → the card alone, carrying what the style would have shown (chips, keys, value).
"""
from __future__ import annotations

import re

from typing import Optional

from engine.schema.messages import Box, Card, Display, Guide, Line, ShowMe, StepInfo
from engine.schema.tutorial import Step, Tutorial

_FIRST = {"click": "outline", "draw_line": "ghost_line", "drag": "ghost_line", "type": "code_card",
          "shortcut": "keycaps", "pick": "mask", "menu_path": "path_chips", "switch_app": "taskbar",
          "wait": "signal_card", "look": "card"}
_REPEAT = {"outline": "beacon", "ghost_line": "static_line"}
# Styles that draw nothing useful without a target on screen.
_NEEDS_TARGET = {"outline", "beacon", "ghost_line", "static_line", "ghost_text", "mask", "path_chips",
                 "taskbar", "click_type"}
_LINE_STYLES = {"ghost_line", "static_line"}
_COMPACT = {"beacon", "static_line"}   # repeats: the light guide + a one-line card (title, Up next, Next)
# Wait steps advance by themselves (live/verify.py: the window settles, plus the step's hint if it has one).
WAIT_AUTO = True
EDGE_INSET = 28      # px from the display edge for the off-screen pill
GEOMETRY = {"canvas", "edge", "face"}
MASK_MIN_PX = 44     # a picked point is tiny: the mask stays big enough to see


def click_type(params: dict) -> Optional[dict]:
    """params.click_type (right | double | ctrl | shift | alt, or combos like ctrl+right) → mouse-icon spec."""
    raw = params.get("click_type")
    if not raw:
        return None
    parts = [p.strip().lower() for p in str(raw).replace("-", "+").split("+") if p.strip()]
    button, count, mods = "left", 1, []
    for p in parts:
        if p in ("right", "right_click", "rightclick"):
            button = "right"
        elif p in ("double", "double_click", "doubleclick"):
            count = 2
        elif p in ("ctrl", "control", "shift", "alt"):
            mods.append({"control": "Ctrl"}.get(p, p.capitalize()))
    if button == "left" and count == 1 and not mods:
        return None
    label = " + ".join(mods + [{("right", 1): "Right-click", ("left", 2): "Double-click",
                                ("right", 2): "Double right-click"}.get((button, count), "click")])
    return {"button": button, "count": count, "modifiers": mods, "label": label}


def _click_key(ct: dict) -> tuple:
    return ct["button"], ct["count"], tuple(ct["modifiers"])


class Planner:
    def __init__(self, tutorial: Tutorial):
        self.tutorial = tutorial
        self.of = len(tutorial.steps)
        self._repeat: dict[int, bool] = {}
        self._first_click_type: dict[int, bool] = {}
        seen_targets: set[tuple] = set()
        seen_clicks: set[tuple] = set()
        for s in tutorial.steps:
            key = (_FIRST[s.action], s.target.label.strip().lower())
            self._repeat[s.n] = s.repeat_of is not None or key in seen_targets
            seen_targets.add(key)
            ct = click_type(s.params)
            if ct:
                self._first_click_type[s.n] = _click_key(ct) not in seen_clicks
                seen_clicks.add(_click_key(ct))

    def is_repeat(self, n: int) -> bool:
        return self._repeat.get(n, False)

    # ---------- the rule ----------
    def style(self, step: Step) -> str:
        style = _FIRST[step.action]
        if style == "mask" and step.target.kind not in GEOMETRY:     # a row in a list isn't geometry: outline it
            style = "outline"
        if self.is_repeat(step.n) and style in _REPEAT:
            style = _REPEAT[style]
        if style == "outline" and self._first_click_type.get(step.n):
            style = "click_type"
        return style

    def plan(self, step: Step, box: Optional[Box] = None, line: Optional[Line] = None,
             displays: Optional[list[Display]] = None, scheme: str = "light") -> Guide:
        style = self.style(step)
        extra = self._extra(step, style)
        if style in _LINE_STYLES and line is None:
            style = "outline" if box is not None else "card"     # no path pinned: point at the box instead
        if style in _NEEDS_TARGET and box is None and line is None:
            if style == "beacon":
                extra = self._extra(step, "outline")
            style = "card"

        if style == "mask" and box is not None:
            box = grown(box, MASK_MIN_PX)

        if box is not None and displays and not any(_intersects(box, d) for d in displays):
            extra = {**extra, **_edge(box, displays), "original_style": style}
            style = "offscreen"

        card = self._card(step, style, box is not None or line is not None)
        return Guide(
            step=StepInfo(n=step.n, of=self.of, title=step.title, part=step.part,
                          source_t=step.source.t, confidence=step.confidence),
            style=style, scheme=scheme, box=box, line=line, extra=extra, card=card)

    def _extra(self, step: Step, style: str) -> dict:
        p = step.params
        x: dict = {"action": step.action, "label": step.target.label}
        ct = click_type(p)
        if ct and self._first_click_type.get(step.n):
            x["click_type"] = ct
        if step.action == "type":
            value = p.get("value")
            if value is None and isinstance(p.get("suggested"), dict):
                value = p["suggested"].get("value")
            if value is not None:
                x["value"] = str(value)
                x["multiline"] = "\n" in str(value).rstrip("\n")
            if p.get("then_key"):
                x["then_key"] = p["then_key"]
        keys = p.get("keys") or (step.target.shortcut.split("+") if step.action == "shortcut" and step.target.shortcut else None)
        if keys:
            x["keys"] = [str(k).strip() for k in keys]
        if step.action == "menu_path" or style == "path_chips":
            x["path"] = step.target.menu_path or [step.target.label]
            x["path_done"] = 0
        if step.target.shortcut and step.action != "shortcut":
            x["shortcut"] = step.target.shortcut
        if step.action == "wait":
            x["signals"] = [str(s) for s in p.get("signals", [])] or ["Screen settled"]
        if step.action == "switch_app":
            x["app"] = step.target.label
        for k in ("length", "direction", "from", "to"):
            if k in p and isinstance(p[k], (str, int, float)):
                x[k] = str(p[k])
        if step.action in ("draw_line", "drag"):
            pill = p.get("length") or _first_value(p.get("suggested"))
            if pill:
                x["pill"] = str(pill)
        return x

    def _card(self, step: Step, style: str, has_target: bool) -> Card:
        p = step.params
        meta = f"Step {step.n} of {self.of} · {self.tutorial.meta.app}"
        if style in _COMPACT:
            nxt = self.tutorial.steps[step.n] if step.n < self.of else None
            return Card(meta=meta, title=step.title, actions=["next"], compact=True,
                        up_next=nxt.title if nxt else None, low_confidence=step.confidence in ("low", "inferred"))
        actions = []
        if has_target and style not in ("signal_card", "card", "offscreen"):
            actions.append("show_me")
        # Do it for me (live/execute.py) is added by the player: it depends on what was found, right now.
        actions.append("skip_wait" if style == "signal_card" and WAIT_AUTO else "next")
        suggested = p.get("suggested")
        return Card(
            meta=meta,
            title=f"Bring {step.target.label} into view" if style == "offscreen" else step.title,
            why=step.why,
            detail=_detail(step, style),
            done_when=step.check,
            suggested=_fmt_suggested(suggested, self.tutorial.meta.units) if suggested else None,
            actions=actions,
            low_confidence=step.confidence in ("low", "inferred"),
        )

    # ---------- Show me ----------
    def show_me(self, step: Step, box: Optional[Box], line: Optional[Line]) -> Optional[ShowMe]:
        ct = click_type(step.params) or {}
        click = "right" if ct.get("button") == "right" else "double" if ct.get("count") == 2 else "left"
        if line is not None and step.action in ("draw_line", "drag"):
            return ShowMe(to=line.end, path=[line.start, line.end], click="none")
        if box is None:
            return None
        if step.action == "type":
            return ShowMe(to=line_start(box), click="left")
        return ShowMe(to=box.center, click=click)


MENU_W_PX, MENU_H_PX = 520, 640     # room a context menu takes, right of and below where you right-click
DROP_MARGIN_PX, DROP_W_PX, DROP_H_PX = 40, 460, 340    # …and a dropdown, under the control that opens it


def avoid_areas(step: Step, box: Optional[Box], extra: dict) -> list[dict]:
    """Where you're about to work, so the card keeps off it (physical px, like the box):
    - typing: the lines the code goes on, from the target line down (the code pushes what's below it down);
    - a right-click route: the context menu that opens at the target.
    The outline itself is always avoided by the overlay; this is what appears next to it."""
    if box is None:
        return []
    out: list[dict] = []
    if step.action == "type":
        value = str(step.params.get("value") or "")
        n = 1 if extra.get("insert") == "col" else max(1, len(value.rstrip("\n").split("\n")))
        lh = float(extra.get("line_h") or box.h)
        clip = extra.get("clip")
        bottom = box.y + box.h + (n - 1) * lh
        if clip:
            bottom = min(bottom, clip["y"] + clip["h"])
        if n > 1 or extra.get("insert") in ("before", "end"):
            out.append({"x": box.x, "y": box.y, "w": box.w, "h": int(max(box.h, bottom - box.y))})
    if step.action == "menu_path" and (click_type(step.params) or {}).get("button") == "right":
        out.append({"x": box.x + box.w // 2, "y": box.y + box.h // 2, "w": MENU_W_PX, "h": MENU_H_PX})
    elif step.action == "menu_path" and extra.get("path"):      # the dropdown that opens under the chip's control
        out.append({"x": box.x - DROP_MARGIN_PX, "y": box.y + box.h, "w": box.w + DROP_W_PX, "h": DROP_H_PX})
    return out


def grown(box: Box, side: int) -> Box:
    """The box, centred where it was, at least `side` px each way."""
    w, h = max(box.w, side), max(box.h, side)
    return Box(x=box.x - (w - box.w) // 2, y=box.y - (h - box.h) // 2, w=w, h=h)


def line_start(box: Box) -> tuple[int, int]:
    """Where to click to type on an editor line: its very start. An empty VS Code file shows hint links
    across its first lines ("Generate code", "select a language"); a click on one opens a picker instead of
    placing the caret, and they start a few px into the line."""
    if box.w > 4 * box.h:
        return box.x + 8, box.y + box.h // 2
    return box.center


def _where(step: Step) -> Optional[str]:
    """"index.html, inside <body>" → "in index.html, inside <body>" (the outline shows the spot too);
    "styles.css, end" → "at the end of styles.css (Ctrl+End jumps there)", and the same for top / Ctrl+Home."""
    w = (step.target.where or "").strip()
    m = re.fullmatch(r"([\w.-]+\.\w+)\s*,\s*(?:at the )?(end|bottom|top|start)", w, re.I)
    if m:
        f, spot = m.group(1), m.group(2).casefold()
        return (f"at the end of {f} (Ctrl+End jumps there)" if spot in ("end", "bottom")
                else f"at the top of {f} (Ctrl+Home jumps there)")
    return f"in {w}" if w else None


def _detail(step: Step, style: str) -> Optional[str]:
    p, label = step.params, step.target.label
    a = step.action
    if style == "offscreen":
        return f"{label} is off-screen. Scroll, zoom out or move the window so it shows."
    if a == "type":
        v = p.get("value")
        then = f", then press {p['then_key']}" if p.get("then_key") else f", then {p['then']}" if p.get("then") else ""
        how = f" ({p['how']})" if p.get("how") else ""
        if v is None and isinstance(p.get("suggested"), dict):
            v = p["suggested"].get("value")
            if v is not None:
                return f"Type {v} in {label}{then}."     # labelled as ours just below, under Suggested
        if v is None:
            return f"Type the value in {label}{then}."
        v = str(v)
        if how:
            return f"Type “{v}”{how}{then}."
        if "\n" in v.rstrip("\n") or len(v) > 40:
            where = _where(step)
            return f"Copy this, or type it, {where}{then}." if where else f"Copy this, or type it, in {label}{then}."
        return f"Type “{v}”{then}."
    if a == "shortcut":
        keys = p.get("keys") or []
        return "Press " + " + ".join(map(str, keys)) + "." if keys else None
    if a == "menu_path":
        path = step.target.menu_path or [label]
        return "Route: " + " › ".join(path)
    if a == "switch_app":
        return f"Switch to {label}. Or press Alt + Tab."
    if a == "wait":
        return "We'll move on when it finishes." if WAIT_AUTO else "When it has loaded, press Next."
    if a == "pick":
        field = p.get("field")
        return f"Click {label}" + (f" (goes into {field})." if field else ".")
    if a in ("draw_line", "drag"):
        bits = [f"from {p['from']}" if p.get("from") else "", f"{p['direction']}" if p.get("direction") else "",
                f"to {p['to']}" if p.get("to") else ""]
        s = " ".join(b for b in bits if b)
        return ("Drag " + s + ".") if s else None
    if a == "click":
        ct = click_type(p)
        return f"{ct['label']} {label}." if ct else None
    return None


def _fmt_suggested(s, units: Optional[str] = None) -> str:
    """{value: "2", side: inside} → "2 mm, side inside"; {length: 100mm} → "length 100mm"."""
    if isinstance(s, dict):
        return ", ".join((f"{v} {units}" if units else str(v)) if k == "value" else f"{k.replace('_', ' ')} {v}"
                         for k, v in s.items())
    return str(s)


def _first_value(s) -> Optional[str]:
    if isinstance(s, dict) and s:
        return str(next(iter(s.values())))
    return None


def _intersects(b: Box, d: Display) -> bool:
    return b.x < d.x + d.w and b.x + b.w > d.x and b.y < d.y + d.h and b.y + b.h > d.y


def _edge(box: Box, displays: list[Display]) -> dict:
    """Nearest display, the point on its edge closest to the target, and which way the target lies."""
    cx, cy = box.center

    def dist(d: Display) -> float:
        dx = max(d.x - cx, 0, cx - (d.x + d.w))
        dy = max(d.y - cy, 0, cy - (d.y + d.h))
        return dx * dx + dy * dy

    d = min(displays, key=dist)
    ex = min(max(cx, d.x + EDGE_INSET), d.x + d.w - EDGE_INSET)
    ey = min(max(cy, d.y + EDGE_INSET), d.y + d.h - EDGE_INSET)
    dx, dy = cx - ex, cy - ey
    direction = ("right" if dx > 0 else "left") if abs(dx) >= abs(dy) else ("down" if dy > 0 else "up")
    return {"edge_point": [ex, ey], "direction": direction, "display": d.id}
