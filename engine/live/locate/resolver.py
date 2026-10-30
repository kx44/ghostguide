"""The finder (live step 4): four ways to find a step's control, cheapest first, stopping at the first sure one.

  4a app map     remembered box from the local layer (learned after a checked step)     instant, a hint
  4b UIA         the app's rule pack (VS Code: locate/vscode.py), else label + aliases   free, exact
  4c Spark       vision on a screenshot (locate/vision.py)                              paid, off by default
  4d route       menu path / shortcut from the step or the app map (locate/menu.py)     no box: path chips

UIA runs before the remembered box is used, because it's exact and cheap here; the remembered box only stands
in when UIA has nothing (a control UIA can't see), and it's what `quick()` can draw before UIA answers. When
both answer, UIA wins and the app map learns from it after the step checks done (`learn`).

Same interface as the old VS Code locator (`locate`, `last_how`, `last_extra`, `last_els`, `last_t`), so the
player and server didn't change.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from engine.live.locate import appmap_hit, menu, uia
from engine.schema.messages import Box, Line
from engine.schema.tutorial import Step


class GenericUIA:
    """UIA stage for apps without a rule pack: the label or one of its app-map aliases, among the control types
    the target's kind allows, in the app's own window."""

    def __init__(self, window: str, store=None, dump=None):
        self.window = window
        self.store = store
        self.dump = dump or (lambda w: uia.dump(w))
        self.last_how = ""
        self.last_extra: dict = {}
        self.last_els: list[dict] = []
        self.last_t = 0.0

    def locate(self, step: Step) -> tuple[Optional[Box], Optional[Line]]:
        self.last_extra = {}
        if step.target.kind in uia.NOT_UIA:
            self.last_how = f"{step.target.kind}: not a UIA control"
            return None, None
        els = self.dump(self.window)
        self.last_els, self.last_t = els, time.monotonic()
        names = self.store.names(step.target.label) if self.store else [step.target.label]
        names += list(step.target.aliases or [])
        el = uia.find_named(els, names, step.target.kind)
        if el is None:
            self.last_how = "not found"
            return None, None
        self.last_how = "named control" if uia.norm(el.get("name")) == uia.norm(step.target.label) else f"alias '{el['name']}'"
        return uia.box_of(el), None


class Resolver:
    def __init__(self, uia_stage, store=None, find_window: Optional[Callable[[str], Optional[tuple]]] = None,
                 vision=None):
        self.uia = uia_stage                 # VSCodeLocator or GenericUIA
        self.store = store                   # appmap.store.AppMapStore
        self.find_window = find_window       # title part → window rect, for remembered boxes
        self.vision = vision                 # SparkVision, or None while FINDER_VISION is off
        self.window = getattr(uia_stage, "window", "")
        self.last_how = ""
        self.last_stage = ""
        self.last_extra: dict = {}
        self.last_seconds = 0.0

    # the old locator's attributes, read by the player and the step check
    @property
    def last_els(self):
        return getattr(self.uia, "last_els", [])

    @property
    def last_t(self):
        return getattr(self.uia, "last_t", 0.0)

    def quick(self, step: Step) -> Optional[Box]:
        """4a alone: instant, for a first draw before UIA has answered."""
        return appmap_hit.remembered(step, self.store, self.find_window) if self.find_window else None

    def locate(self, step: Step) -> tuple[Optional[Box], Optional[Line]]:
        t0 = time.perf_counter()
        try:
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
        hit = self.quick(step)
        if hit is not None:
            self.last_how, self.last_stage = f"remembered from a checked run ({why})", "appmap"
            return hit, None
        if self.vision is not None:
            b = self.vision.find(step)
            if b is not None:
                self.last_how, self.last_stage = self.vision.last_how, "vision"
                return b, None
        r = menu.route(step, self.store)
        if r is not None and step.action != "menu_path":   # menu_path steps already show their chips
            self.last_extra["route"] = r
            self.last_how, self.last_stage = f"{why}; {menu.describe(r)}", "route"
            return None, None
        self.last_how, self.last_stage = why, "none"
        return None, None

    def learn(self, step: Step, box: Box) -> bool:
        """After the step checked done: remember a stable control's box, relative to its window."""
        if self.store is None or self.find_window is None or not appmap_hit.learnable(step):
            return False
        rect = self.find_window(self.window)
        if rect is None:
            return False
        return self.store.learn(step.target.label, self.window, (box.x, box.y, box.w, box.h), rect)
