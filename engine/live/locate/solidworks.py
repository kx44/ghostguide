"""The UIA stage for SolidWorks. What UI Automation sees there (checked on 2026 SP4.1): the FeatureManager tree
items, the PropertyManager tab, dialogs and menus, but not one ribbon button, so the ribbon and the canvas go on to
Spark vision. Dialogs and flyouts are their own top-level windows, so the dump takes every SOLIDWORKS window.

The matching is pure over dumped element dicts, so it's tested off Windows.
"""
from __future__ import annotations

import time
from typing import Optional

from engine.live.locate import uia
from engine.live.locate.resolver import GenericUIA
from engine.schema.messages import Box, Line
from engine.schema.tutorial import Step

WINDOW = "SOLIDWORKS"


def dump_all(window: str) -> list[dict]:
    return uia.dump(window, every=True)


def tree_item(els: list[dict], label: str) -> Optional[dict]:
    """The FeatureManager row. The flyout tree repeats the names; the last visible match sits on top of the main
    tree when it's open, and is the main tree's row when it isn't."""
    want = uia.norm(label)
    hits = [e for e in els if e.get("type") == "TreeItem" and uia.norm(e.get("name")) == want and uia.visible(e)]
    return hits[-1] if hits else None


class SolidWorksUIA(GenericUIA):
    def __init__(self, window: str = WINDOW, store=None, dump=None):
        super().__init__(window, store, dump or dump_all)

    def locate(self, step: Step, label: Optional[str] = None) -> tuple[Optional[Box], Optional[Line]]:
        if step.target.kind == "tree_item" and label is None:
            self.last_extra = {}
            self.last_els, self.last_t = self.dump(self.window), time.monotonic()
            el = tree_item(self.last_els, step.target.label)
            if el is not None:
                self.last_how = "tree row"
                return uia.box_of(el), None
            self.last_how = "no such row in the tree yet"
            return None, None
        return super().locate(step, label)
