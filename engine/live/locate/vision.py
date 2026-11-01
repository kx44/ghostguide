"""Finder stage 4c: Spark vision. A screenshot of the app, the target's label and `where`, and Spark answers by
calling our tools: `point_at` (a box), `draw_line` (a ghost line on the canvas) or `menu_path` (a route). We map
screenshot pixels back to the screen.

**Off** unless FINDER_VISION=on: it's for apps without good accessibility data (SolidWorks' ribbon and canvas),
and every call costs credits. Calls go through models/client.py, so MODEL_MODE (record / replay) and the $4
budget cap apply; in replay mode an unrecorded request is simply a miss.

The finder re-asks every second, so this stage remembers: an answer stands while the pixels around it haven't
changed, a miss stands while the window hasn't changed, and one target never gets more than MAX_CALLS calls.

`regions` (SolidWorks): the ribbon, the PropertyManager and the corners are small and dense, so Spark sees just
that part of the window at higher resolution instead of the whole window scaled down.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from engine import config
from engine.live.locate.menu import named_tab
from engine.models.tools import LOCATE_TOOLS, DrawLine, MenuPath, PointAt
from engine.schema.messages import Box, Line
from engine.schema.tutorial import Step

# Spark's reasoning counts toward max_tokens, so leave room beyond the tool call.
MAX_TOKENS = 2048
EFFORT = config.env("FINDER_EFFORT", "low")
MAX_CALLS = 3            # per target, per run of a step
MAX_REFUNDS = 3          # looks a tooltip's "no" can give back, per target
MIN_GAP_S = 3.0          # between calls for one target
SAME_SHARE = 0.35        # the patch around an answer may change this much (a hover highlight) and still stand
PAD_PX = 24              # around an answer, for that patch
MAX_BOX_SHARE = 0.25     # a "control" bigger than this share of the picture isn't one
FULL_W = 1280            # picture width for the whole window
REGION_W = 2048          # …for a region: as sharp as we can afford
PROMPT = ("This is a screenshot of {app}, {what}, {w} pixels wide and {h} pixels tall. Find the control for this "
          "tutorial step and call point_at with its box in screenshot pixels: tight around that one control, its "
          "icon and text together. Read the text labels: similar icons sit side by side. If it isn't visible, call "
          "menu_path with the route to it (a ribbon tab name first, if it's on a ribbon tab that isn't open), or "
          "not_found. Never point at a different control.\n"
          "Step: {title}\nControl: {label} ({kind})\nWhere: {where}")
ZOOM = 2                 # the second look: this much larger…
ZOOM_PAD_X, ZOOM_PAD_Y = 240, 120      # …around the first answer (window px)
PROMPT_ZOOM = ("This is an enlarged part of a screenshot of {app}, {w} pixels wide and {h} pixels tall. Call point_at "
               "with a box in these pixels, tight around this control: {label} ({kind}), its icon and text together, nothing "
               "else. Read the text labels; if it's a small icon with no text, go by the description: {where}. If it "
               "isn't in this picture, call not_found.")
PROMPT_LINE = ("This is a screenshot of {app}, {what}, {w} pixels wide and {h} pixels tall. The user has to draw "
               "this line with the mouse in the graphics area. Call draw_line with its start and end in screenshot "
               "pixels. The sketch origin is where the red arrows meet.\n"
               "Step: {title}\nStart near: {label} ({where})\nHow: {how}")
PROMPT_PICK = ("This is a screenshot of {app}, {what}, {w} pixels wide and {h} pixels tall. The user has to pick this "
               "geometry in the graphics area. Call point_at with a box tight around it (for a point, a small box "
               "centred on it), or not_found if it isn't there.\n"
               "Step: {title}\nGeometry: {label} ({kind})\nWhere: {where}")

PROMPT_HOP = ("This is a screenshot of {app}, {what}, {w} pixels wide and {h} pixels tall. The user is following this "
              "route: {route}. Call point_at with a box tight around the next thing to click: \"{label}\". It may be a "
              "ribbon tab name, an item in an open dropdown or menu, or a small icon with no text on a toolbar (use what "
              "you know of the app's icons). If it isn't visible, call not_found.\nWhere the tutorial says it is: {where}")

# Regions in DIPs from the window's edges (SolidWorks' layout; the frame scales with the display, not the window).
RIBBON_H = 125
PANEL_TOP, PANEL_W = 85, 300
CORNER_W, CORNER_H = 0.45, 240
HEADSUP_H = 70
NEAR_LEFT, NEAR_UP, NEAR_W, NEAR_H = 240, 40, 1100, 680     # around the control whose menu opened, window px
TAB_TOP, TAB_H = 115, 19     # the row of ribbon tab names: thin, and Spark's y is off by more than its height


def enabled() -> bool:
    return config.env("FINDER_VISION", "off").lower() in ("on", "1", "true", "yes")


def to_screen(p: PointAt, scale: float, origin: tuple[int, int]) -> Box:
    """Screenshot px (taken at `scale`, top-left at screen `origin`; p.x/p.y = center) → physical screen px box."""
    ox, oy = origin
    return Box(x=round(ox + (p.x - p.w / 2) / scale), y=round(oy + (p.y - p.h / 2) / scale),
               w=max(1, round(p.w / scale)), h=max(1, round(p.h / scale)))


def line_to_screen(d: DrawLine, scale: float, origin: tuple[int, int]) -> Line:
    ox, oy = origin
    return Line(start=(round(ox + d.x1 / scale), round(oy + d.y1 / scale)),
                end=(round(ox + d.x2 / scale), round(oy + d.y2 / scale)))


def region_for(step: Step) -> str:
    """Which part of the window a target is in, from its `where`."""
    w = (step.target.where or "").casefold()
    if step.target.kind in ("canvas", "face", "edge"):
        return "window"
    if "propertymanager" in w:
        return "panel"
    if "confirmation corner" in w or ("corner" in w and re.search(r"\b(upper|top)[ -](right|hand)", w)) or "upper right" in w:
        return "corner"                     # also how a tutorial says it: "upper right-hand corner of workspace"
    if "heads-up" in w or re.search(r"\b(above the (working|graphics) area|top of (the )?(workspace|graphics))", w):
        return "headsup"                    # "icons above the working area", "icon at top of workspace"
    if "commandmanager" in w or "toolbar" in w:
        return "ribbon"                     # "top toolbar", and as tutorials often say it, "Sketch toolbar"
    return "window"


def region_box(name: str, w: int, h: int, s: float) -> tuple[int, int, int, int]:
    """(x, y, w, h) of a region in a window image `w`×`h`, at display scale `s`."""
    if name == "ribbon":
        return 0, 0, w, min(h, round(RIBBON_H * s))
    if name == "panel":
        top = round(PANEL_TOP * s)
        return 0, top, min(w, round(PANEL_W * s)), max(1, h - top)
    if name == "corner":
        x, top = round(w * (1 - CORNER_W)), round(PANEL_TOP * s)
        return x, top, w - x, min(h - top, round(CORNER_H * s))
    if name == "headsup":
        top = round(PANEL_TOP * s)
        return 0, top, w, min(h - top, round(HEADSUP_H * s))
    return 0, 0, w, h


REGION_WORDS = {"ribbon": "its ribbon and top toolbar only", "panel": "its left panel only",
                "corner": "the top-right corner of its graphics area only",
                "headsup": "the toolbar across the top of its graphics area only", "window": "the whole window"}


def picture(img, name: str, s: float, full_w: int = FULL_W, region_w: int = REGION_W):
    """The region as (PNG bytes, scale, (x, y) of its corner in the window image, its size)."""
    from engine.live.capture import for_model

    x, y, w, h = region_box(name, img.width, img.height, s)
    part = img if (x, y, w, h) == (0, 0, img.width, img.height) else img.crop((x, y, x + w, y + h))
    png, scale = for_model(part, full_w if name == "window" else region_w)
    return png, scale, (x, y), (round(w * scale), round(h * scale))


def how_to_draw(p: dict) -> str:
    bits = [f"{k.replace('_', ' ')}: {v}" for k, v in p.items() if k in ("from", "to", "direction", "segments", "suggested")]
    return "; ".join(bits) or "-"


@dataclass
class _Memo:
    calls: int = 0
    refunds: int = 0             # looks given back because a tooltip said no
    t: float = -1e9
    box: Optional[Box] = None
    line: Optional[Line] = None
    route: Optional[dict] = None
    how: str = ""
    conf: str = ""
    not_it: list = field(default_factory=list)      # what tooltips said about the boxes this target has been given
    on_nothing: bool = False     # a box it gave showed no tooltip: it wasn't on a button
    patch: object = None         # the pixels around the answer, or the whole window for a miss
    patch_at: tuple = (0, 0, 0, 0)


class SparkVision:
    def __init__(self, app: str, client=None, grab: Optional[Callable[[], Optional[tuple]]] = None,
                 regions: bool = False, clock: Callable[[], float] = time.monotonic, max_calls: int = MAX_CALLS):
        self.app = app
        self.client = client
        self.grab = grab            # () → (PIL image, screen origin of it, display scale), or None
        self.regions = regions
        self.clock = clock
        self.max_calls = max_calls
        self.last_how = ""
        self.last_line: Optional[Line] = None
        self.last_route: Optional[dict] = None
        self.last_conf = ""
        self._memo: dict[tuple, _Memo] = {}

    def forget(self, n: int) -> None:
        """The step is showing again: a fresh allowance of calls."""
        for k in [k for k in self._memo if k[0] == n]:
            del self._memo[k]

    def reject(self, n: int, label: str, shown: str) -> None:
        """A tooltip says that box is something else: look again, and that look is on us, not on the allowance."""
        memo = self._memo.setdefault((n, label), _Memo())
        memo.box, memo.line, memo.patch = None, None, None
        if memo.refunds < MAX_REFUNDS:      # a limit, or a tooltip that keeps saying no is a paid look every few seconds, for ever
            memo.refunds += 1
            memo.calls = max(0, memo.calls - 1)
        memo.t = 0.0
        if shown not in memo.not_it:
            memo.not_it.append(shown)

    def empty(self, n: int, label: str) -> None:
        """No tooltip came at that box, so it isn't on a button. Look again, from the same allowance: this can't go on for ever."""
        memo = self._memo.setdefault((n, label), _Memo())
        memo.box, memo.line, memo.patch = None, None, None
        memo.t = 0.0
        memo.on_nothing = True

    def spent(self, n: int, label: str) -> bool:
        """Has this target had all its calls?"""
        memo = self._memo.get((n, label))
        return memo is not None and memo.calls >= self.max_calls

    def find(self, step: Step, label: Optional[str] = None, route: Optional[list[str]] = None,
             hop: int = 0, near: Optional[Box] = None) -> Optional[Box]:
        """`route` + `hop`: looking for that hop of a route, rather than for the step's own control. `near`: the box
        of the hop before it, whose menu this is: a menu opens right there, so that part of the window is enough."""
        self.last_line, self.last_route, self.last_conf = None, None, ""
        if self.grab is None:
            self.last_how = "vision: no screenshot"
            return None
        shot = self.grab()
        if shot is None:
            self.last_how = "vision: window not visible"
            return None
        img, origin, s = shot
        key = (step.n, label or step.target.label)
        memo = self._memo.setdefault(key, _Memo())
        if self._still_good(memo, img, origin) or memo.calls >= self.max_calls or self.clock() - memo.t < MIN_GAP_S:
            return self._answer(memo)
        self._ask(step, label or step.target.label, img, origin, s, memo, route, hop, near)
        return self._answer(memo)

    def _answer(self, memo: _Memo) -> Optional[Box]:
        self.last_how, self.last_line, self.last_route, self.last_conf = memo.how or "vision: nothing yet", memo.line, memo.route, memo.conf
        return memo.box

    def _still_good(self, memo: _Memo, img, origin) -> bool:
        from engine.live.capture import changed, changed_share, crop
        if memo.patch is None:
            return False
        if memo.box is None and memo.line is None:     # a miss gets more tries (Spark's answers vary on small
            if memo.calls < self.max_calls:            # icons), then stands until the window changes
                return False
            return memo.patch.size == img.size and not changed(memo.patch, img)
        now = crop(img, memo.patch_at, origin, PAD_PX)
        return now.size == memo.patch.size and changed_share(memo.patch, now) <= SAME_SHARE

    def _ask(self, step: Step, label: str, img, origin, s: float, memo: _Memo, route=None, hop: int = 0, near=None) -> None:
        from engine.live.capture import crop, for_model
        from engine.models.client import ModelClient, image_part, text_part

        t = step.target
        # A route's last hop is an item in a menu, which can open anywhere; the ones before it are still in the ribbon.
        last_hop = bool(route) and hop == len(route) - 1
        region = region_for(step) if self.regions and not last_hop else "window"
        if near is not None:
            x0, y0 = max(0, near.x - origin[0] - NEAR_LEFT), max(0, near.y - origin[1] - NEAR_UP)
            part = img.crop((x0, y0, min(img.width, x0 + NEAR_W), min(img.height, y0 + NEAR_H)))
            png, scale = for_model(part, NEAR_W)
            rx, ry, w, h = x0, y0, part.width, part.height
        else:
            png, scale, (rx, ry), (w, h) = picture(img, region, s)
        at = (origin[0] + rx, origin[1] + ry)
        fields = dict(app=self.app, what="part of its window" if near is not None else REGION_WORDS[region], w=w, h=h, title=step.title, label=label, kind=t.kind,
                      where=t.where or "-")
        line_step = step.action in ("draw_line", "drag") and t.kind in ("canvas", "edge", "face")
        is_tab = False
        if route:
            tab = named_tab(t.where)
            is_tab = bool(hop == 0 and tab and tab.casefold() == label.casefold())
            if is_tab:
                fields["label"] = f"the {label} tab, in the row of ribbon tab names under the ribbon (not a button called {label})"
            text = PROMPT_HOP.format(route=" › ".join(route), **fields)
        elif line_step:
            text = PROMPT_LINE.format(how=how_to_draw(step.params), **fields)
        elif step.action == "pick" and t.kind in ("canvas", "edge", "face"):
            text = PROMPT_PICK.format(**fields)
        else:
            text = PROMPT.format(**fields)
        if memo.not_it:
            text += "\nNot these, already checked: " + ", ".join(memo.not_it) + "."
        if memo.on_nothing:
            text += "\nYour last box wasn't on a button: nothing showed a tooltip there. The control is close by. Box the icon itself, tightly."
        memo.calls += 1
        memo.t = self.clock()
        memo.box, memo.line, memo.route, memo.conf = None, None, None, ""
        memo.patch = img
        try:
            c = self.client or ModelClient()
            reply = c.chat(model=config.SPARK, max_tokens=MAX_TOKENS, tools=LOCATE_TOOLS, reasoning_effort=EFFORT,
                           tag=f"find-step-{step.n}",
                           messages=[{"role": "user", "content": [text_part(text), image_part(png)]}])
        except Exception as e:      # replay miss, budget cap, network: a miss, never a crash
            memo.how = f"vision: {e}"[:120]
            return
        memo.how = "vision: Spark didn't point at it"
        for call in reply.tool_calls:
            if isinstance(call, PointAt):
                if call.w * call.h > MAX_BOX_SHARE * w * h:
                    memo.how = "vision: Spark's box was too big to be one control"
                    continue
                memo.box = to_screen(call, scale, at)
                memo.conf, memo.how = call.confidence, f"vision: Spark pointed ({call.confidence})"
                if near is None and not line_step and t.kind not in ("canvas", "edge", "face"):
                    self._refine(step, fields["label"], img, origin, memo, c)
                    if memo.box is not None and is_tab and self.regions:
                        memo.box = Box(x=memo.box.x, y=origin[1] + round(TAB_TOP * s), w=memo.box.w, h=round(TAB_H * s))
                break
            if isinstance(call, DrawLine):
                memo.line = line_to_screen(call, scale, at)
                memo.conf, memo.how = call.confidence, f"vision: Spark drew the line ({call.confidence})"
                break
            if isinstance(call, MenuPath) and call.path:
                memo.route = {"path": list(call.path), "confidence": call.confidence, "by": "spark"}
                memo.how = "vision: not on screen, Spark gave a route"
                break
        if memo.box is not None or memo.line is not None:
            if memo.line is not None:
                a, b = memo.line.start, memo.line.end
                x, y = min(a[0], b[0]), min(a[1], b[1])
                memo.patch_at = (x, y, abs(a[0] - b[0]) + 1, abs(a[1] - b[1]) + 1)
            else:
                memo.patch_at = (memo.box.x, memo.box.y, memo.box.w, memo.box.h)
            memo.patch = crop(img, memo.patch_at, origin, PAD_PX)

    def _refine(self, step: Step, label: str, img, origin, memo: _Memo, client) -> None:
        """Second look: Spark's first box names the right control but sits loosely on a dense ribbon, so show it
        just that neighbourhood, enlarged, and take the tighter answer. A miss here keeps the first box."""
        import io

        from PIL import Image
        from engine.models.client import image_part, text_part

        b = memo.box
        cx, cy = b.x + b.w // 2 - origin[0], b.y + b.h // 2 - origin[1]
        x0, x1 = max(0, cx - ZOOM_PAD_X), min(img.width, cx + ZOOM_PAD_X)
        y0, y1 = max(0, cy - ZOOM_PAD_Y), min(img.height, cy + ZOOM_PAD_Y)
        if x1 <= x0 or y1 <= y0:
            return
        part = img.crop((x0, y0, x1, y1)).resize(((x1 - x0) * ZOOM, (y1 - y0) * ZOOM), Image.LANCZOS)
        buf = io.BytesIO()
        part.convert("RGB").save(buf, format="PNG")
        text = PROMPT_ZOOM.format(app=self.app, w=part.width, h=part.height, label=label, kind=step.target.kind,
                                  where=step.target.where or "-")
        try:
            reply = client.chat(model=config.SPARK, max_tokens=MAX_TOKENS, tools=LOCATE_TOOLS, reasoning_effort=EFFORT,
                                tag=f"find-step-{step.n}-zoom",
                                messages=[{"role": "user", "content": [text_part(text), image_part(buf.getvalue())]}])
        except Exception:
            return
        for call in reply.tool_calls:
            if isinstance(call, PointAt) and call.w * call.h <= 0.8 * part.width * part.height:
                memo.box = to_screen(call, ZOOM, (origin[0] + x0, origin[1] + y0))
                memo.conf, memo.how = call.confidence, f"vision: Spark pointed, zoomed in ({call.confidence})"
                return
        # Close up, it isn't there: the first look was at something else. A miss, which gets another try.
        memo.box, memo.conf, memo.how = None, "", "vision: the closer look didn't find it"
