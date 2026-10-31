"""The finder (live step 4): the ways to find a step's control, cheapest first, stopping at the first sure one.

  4a app map     remembered box from the local layer (learned after a checked step)     instant, a hint
  4b UIA         the app's rule pack (VS Code, SolidWorks), else label + aliases         free, exact
  4c Spark       vision on a screenshot (locate/vision.py)                              paid, off by default
  4d route       menu path / shortcut from the step or the app map (locate/menu.py)     no box: path chips
  4e Wonder      a route (or box) for a control nobody knows (locate/menu.py)           paid, once per step

UIA runs before the remembered box is used, because it's exact and cheap here; the remembered box only stands
in when UIA has nothing (a control UIA can't see), and it's what `quick()` can draw before UIA answers. When
both answer, UIA wins and the app map learns from it after the step checks done (`learn`).

With a route in hand the outline goes on the route's next hop, when vision can see it: the ribbon tab to open, the
next menu item. `menu_path` steps do the same, chip by chip.

Same interface as the old VS Code locator (`locate`, `last_how`, `last_extra`, `last_els`, `last_t`), so the
player and server didn't change.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from engine.live.locate import appmap_hit, menu, uia
from engine.schema.messages import Box, Line
from engine.schema.tutorial import Step


NOTHING_TO_CLICK = ("shortcut", "wait", "look")
DROP_ARROW_PX = 9     # the small dropdown arrow, this far past a ribbon button's icon


class GenericUIA:
    """UIA stage for apps without a rule pack: the label or one of its app-map aliases, among the control types
    the target's kind allows, in the app's own window."""
    follows_hops = True          # `locate` takes the name of a route's next chip

    def __init__(self, window: str, store=None, dump=None):
        self.window = window
        self.store = store
        self.dump = dump or (lambda w: uia.dump(w))
        self.last_how = ""
        self.last_extra: dict = {}
        self.last_els: list[dict] = []
        self.last_t = 0.0

    def locate(self, step: Step, label: Optional[str] = None) -> tuple[Optional[Box], Optional[Line]]:
        self.last_extra = {}
        if step.target.kind in uia.NOT_UIA:
            self.last_how = f"{step.target.kind}: not a UIA control"
            return None, None
        els = self.dump(self.window)
        self.last_els, self.last_t = els, time.monotonic()
        label = label or step.target.label
        names = self.store.names(label) if self.store else [label]
        names += list(step.target.aliases or [])
        el = uia.find_named(els, names, step.target.kind)
        if el is None:
            self.last_how = "not found"
            return None, None
        self.last_how = "named control" if uia.norm(el.get("name")) == uia.norm(label) else f"alias '{el['name']}'"
        return uia.box_of(el), None


class Resolver:
    def __init__(self, uia_stage, store=None, find_window: Optional[Callable[[str], Optional[tuple]]] = None,
                 vision=None, wonder=None, hops: Optional[menu.Hops] = None, looks=None, look_of=None, arrow=None):
        self.uia = uia_stage                 # VSCodeLocator, SolidWorksUIA or GenericUIA
        self.store = store                   # appmap.store.AppMapStore
        self.find_window = find_window       # title part → window rect, for remembered boxes
        self.vision = vision                 # SparkVision, or None while FINDER_VISION is off
        self.wonder = wonder                 # menu.Wonder, or None while FINDER_VISION is off
        self.hops = hops or menu.Hops()
        self.looks = looks                   # (box, remembered look) → same pixels? None = don't compare
        self.look_of = look_of               # box → its look, saved when learning
        self.arrow = arrow                   # box → the dropdown arrow beside it, to the pixel
        self.window = getattr(uia_stage, "window", "")
        self._hops_clicked: dict[int, list[tuple]] = {}  # kept until the step checks done: a click can be on the wrong icon
        self._prev_box: dict[int, Optional[Box]] = {}  # the hop before the current one: its menu is what's open
        self._hop_box: dict[int, Optional[Box]] = {}  # the current chip's control, as found (no dropdown arrow)
        self._pending_look: dict[str, list[int]] = {}  # its pixels as first found, before a click changes them
        self._new_route: dict[int, list[str]] = {}    # a route Wonder gave, replacing the tutorial's
        self.last_how = ""
        self.last_stage = ""
        self.last_conf = ""
        self.last_extra: dict = {}
        self.last_seconds = 0.0

    # the old locator's attributes, read by the player and the step check
    @property
    def last_els(self):
        return getattr(self.uia, "last_els", [])

    @property
    def last_t(self):
        return getattr(self.uia, "last_t", 0.0)

    def forget(self, n: int) -> None:
        """The step is showing again: fresh hops and a fresh vision allowance."""
        self.hops.forget(n)
        self._hops_clicked.pop(n, None)
        if self.vision is not None and hasattr(self.vision, "forget"):
            self.vision.forget(n)

    def quick(self, step: Step) -> Optional[Box]:
        """4a alone: instant, for a first draw before UIA has answered. With `looks` (apps whose controls share
        one spot, like SolidWorks' ribbon tabs), the box only counts if it still looks like what was remembered."""
        if not self.find_window:
            return None
        box = appmap_hit.remembered(step, self.store, self.find_window)
        if box is not None and self.looks is not None:
            c = self.store.get(step.target.label)
            if c is None or c.seen is None or not self.looks(box, c.seen.look):
                return None
        return box

    def locate(self, step: Step) -> tuple[Optional[Box], Optional[Line]]:
        t0 = time.perf_counter()
        self.last_conf = ""
        try:
            if (getattr(self.uia, "follows_hops", False) and step.action == "menu_path"
                    and len(step.target.menu_path or []) > 1):
                return self._locate_hops(step)
            return self._locate(step)
        finally:
            self.last_seconds = time.perf_counter() - t0

    def _locate(self, step: Step) -> tuple[Optional[Box], Optional[Line]]:
        box, line = self.uia.locate(step)
        self.last_extra = dict(getattr(self.uia, "last_extra", None) or {})
        if box is not None or line is not None:
            self.last_how, self.last_stage = self.uia.last_how, "uia"
            return box, line
        why = self.uia.last_how
        if step.action in NOTHING_TO_CLICK:     # the card alone is the guidance: never pay to look for a control
            self.last_how, self.last_stage = why, "none"
            return None, None
        hit = self.quick(step)
        if hit is not None:
            self.last_how, self.last_stage = f"remembered from a checked run ({why})", "appmap"
            return hit, None
        seen_route = None
        if self.vision is not None:
            b = self.vision.find(step)
            ln = getattr(self.vision, "last_line", None)
            if b is not None or ln is not None:
                self.last_how, self.last_stage = self.vision.last_how, "vision"
                self.last_conf = getattr(self.vision, "last_conf", "")
                return b, ln
            seen_route = getattr(self.vision, "last_route", None)
            if seen_route and seen_route.get("confidence") != "high":
                seen_route = None
        r = menu.route(step, self.store)
        tab = menu.tab_route(step) if getattr(self.uia, "follows_hops", False) else None
        if tab:                     # it's on a closed ribbon tab: closer than any menu, which may be hidden anyway
            r = {**(r or {}), "path": tab}
        if r is not None and not r.get("path") and seen_route:   # a shortcut alone: the route is still worth showing
            r = {**seen_route, **r}
        elif r is None and self.wonder is None:
            r = seen_route
        stage = "route"
        if r is None and self.wonder is not None and self.wonder.wanted(step):
            # Nothing stored. Spark's route is a guess from one look; Wonder's goes to the app map for review.
            b, r = self.wonder.ask(step)
            why = self.wonder.last_how
            stage = "wonder"
            if b is not None:
                self.last_how, self.last_stage = why, stage
                return b, None
            r = r or seen_route
        if r is not None and step.action != "menu_path":   # menu_path steps already show their chips
            self.last_extra["route"] = r
            self.last_how, self.last_stage = f"{why}; {menu.describe(r)}", stage
            return self._first_hop(step, r), None
        self.last_how, self.last_stage = why, "none"
        return None, None

    def _first_hop(self, step: Step, r: dict) -> Optional[Box]:
        """A route with a tab or menu to open first: put the outline on it, when it can be seen."""
        path = r.get("path") or []
        if len(path) < 2 or self.vision is None:
            return None
        return self.vision.find(step, menu.hop_label(path[0]), route=path)

    def _locate_hops(self, step: Step) -> tuple[Optional[Box], Optional[Line]]:
        path = self._new_route.get(step.n) or step.target.menu_path
        before = self.hops._at.get(step.n, 0)
        i = self.hops.current(step.n, path)
        if i > before:                   # that chip was clicked and the route moved on: its box was right
            self._prev_box[step.n] = self._hop_box.pop(step.n, None)
            self._hops_clicked.setdefault(step.n, []).append((menu.hop_label(path[before]), self._prev_box[step.n]))
        label = menu.hop_label(path[i])
        box = self.uia.locate(step, label)[0]
        self.last_extra = {"path_done": i}
        if step.n in self._new_route:
            self.last_extra["path"] = path
        why = self.uia.last_how
        stage = "uia"
        if box is None:
            box = self._remembered(label)
            if box is not None:
                why, stage = "remembered from a checked run", "appmap"
        if box is None and self.vision is not None:
            last = i == len(path) - 1
            box = self.vision.find(step, label, route=path, hop=i, near=self._prev_box.get(step.n) if last else None)
            why, stage = self.vision.last_how, "vision"
            self.last_conf = getattr(self.vision, "last_conf", "")
        self._hop_box[step.n] = box
        if box is not None and stage == "vision" and self.look_of is not None and label not in self._pending_look:
            look = self.look_of(box)
            if look is not None:
                self._pending_look[label] = look
        if box is not None and label != path[i]:
            # A chip with ▾ means the small arrow beside the button: the outline takes both, the click the arrow.
            arrow = self.arrow(box) if self.arrow else None
            if arrow:                                                  # no small arrow: a big button, which opens anywhere
                self.last_extra["click_at"] = arrow
                cx, cy = arrow                                         # the box takes in the arrow, however loose it was
                top, bottom = min(box.y, cy - DROP_ARROW_PX), max(box.y + box.h, cy + DROP_ARROW_PX)
                box = Box(x=box.x, y=top, w=max(box.w, cx - box.x + DROP_ARROW_PX), h=bottom - top)
        spent = getattr(self.vision, "spent", None)
        tried = spent is None or spent(step.n, label)
        if box is None and i == 0 and tried and self.wonder is not None and not step.target.shortcut and step.n not in self._new_route:
            # The tutorial's route isn't on this version's screen: Wonder may know where it went.
            b, r = self.wonder.ask(step)
            if b is not None:
                box, why, stage = b, self.wonder.last_how, "wonder"
                self._hop_box[step.n] = b
            elif r and r.get("path"):
                self._new_route[step.n] = r["path"]
                self.last_extra["path"] = r["path"]
                why, stage = self.wonder.last_how, "wonder"
        if box is None and i > 0 and tried:
            self.hops.back_to_start(step.n)       # it had its tries: the menu must have closed again
            self.last_extra["path_done"] = 0
        self.hops.found(step.n, box)
        self.last_how, self.last_stage = f"hop {i + 1} of {len(path)}, {label}: {why}", stage if box is not None or stage == "wonder" else "none"
        return box, None

    def _remembered(self, label: str) -> Optional[Box]:
        """A route's hop where it was last time, if it still looks the same. Nothing remembered without a look."""
        c = self.store.get(label) if self.store is not None else None
        if c is None or c.seen is None or self.looks is None or not self.find_window:
            return None
        rect = self.find_window(c.seen.window)
        if rect is None:
            return None
        box = appmap_hit.place(c.seen.rel_box, rect)
        return box if self.looks(box, c.seen.look) else None

    def _learn_hop(self, label: str, box: Optional[Box]) -> None:
        if box is None or self.store is None or self.find_window is None or self.look_of is None:
            return
        rect = self.find_window(self.window)
        if rect is not None:
            self.store.learn(label, self.window, (box.x, box.y, box.w, box.h), rect, self._pending_look.pop(label, None))

    def learn(self, step: Step, box: Box) -> bool:
        """After the step checked done: remember a stable control's box, relative to its window."""
        for label, hop_box in self._hops_clicked.pop(step.n, []):
            self._learn_hop(label, hop_box)
        if self.store is None or self.find_window is None or not appmap_hit.learnable(step):
            return False
        if self.last_extra.get("route") or (step.action == "menu_path" and len(step.target.menu_path or []) > 1):
            return False       # the box drawn last was a hop on the way, not the control itself
        rect = self.find_window(self.window)
        if rect is None:
            return False
        look = self.look_of(box) if self.look_of else None
        return self.store.learn(step.target.label, self.window, (box.x, box.y, box.w, box.h), rect, look)
