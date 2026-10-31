"""The UIA stage for SolidWorks. What UI Automation sees there (checked on 2026 SP4.1):

  FeatureManager rows     named TreeItems; a sketch under-defined reads "(-) Sketch1"
  PropertyManager         the title is a named Button ("Offset Entities") or a Text ("Plane"), the green check the first
                          nameless square button under it, the sections are named Buttons, the number fields Edits with a value
  New Document dialog     Part / Assembly / Drawing are three big nameless Buttons, in that order
  the ribbon, flyouts     nothing at all, so those go on to Spark vision
  the canvas              nothing, Spark vision

Dialogs are their own top-level windows, so the dump takes every SOLIDWORKS window. Elements are read by these rules,
pure over dumped dicts, so they're tested off Windows.
"""
from __future__ import annotations

import re
import time
from typing import Optional

from engine.live.locate import uia
from engine.live.locate.resolver import GenericUIA
from engine.schema.messages import Box, Line
from engine.schema.tutorial import Step

WINDOW = "SOLIDWORKS"
NEW_DIALOG = "New SOLIDWORKS Document"
DIALOG_CHOICES = ("part", "assembly", "drawing")
PANEL_MAX_X = 500        # physical px: the PropertyManager's right edge is well inside this at any common scale
_STATE = re.compile(r"^\((?:-|\+|\?|f)\)\s*")          # "(-) Sketch1": how defined the sketch is
OK_LABEL = re.compile(r"^ok\b", re.I)


def dump_all(window: str) -> list[dict]:
    return uia.dump(window, every=True)


def row_name(name: Optional[str]) -> str:
    return uia.norm(_STATE.sub("", (name or "").strip()))


def tree_item(els: list[dict], label: str) -> Optional[dict]:
    """The FeatureManager row. The flyout tree repeats the names; the last visible match sits on top of the main
    tree when it's open, and is the main tree's row when it isn't."""
    want = row_name(label)
    hits = [e for e in els if e.get("type") == "TreeItem" and row_name(e.get("name")) == want and uia.visible(e)]
    return hits[-1] if hits else None


def dialog_choice(els: list[dict], label: str) -> Optional[dict]:
    """Part, Assembly or Drawing in the New Document dialog: big nameless buttons, left to right."""
    want = uia.norm(label)
    if want not in DIALOG_CHOICES:
        return None
    dialog = next((e for e in els if e.get("type") == "Window" and uia.norm(e.get("name")) == uia.norm(NEW_DIALOG)), None)
    if dialog is None:
        return None
    x, y, w, h = dialog["rect"]
    big = [e for e in els if e.get("type") == "Button" and not e.get("name") and uia.visible(e)   # the tall ones, not
           and e["rect"][2] > 120 and e["rect"][3] > 180                                          # the Tutorials banner
           and x <= e["rect"][0] and y <= e["rect"][1] and e["rect"][0] + e["rect"][2] <= x + w and e["rect"][1] + e["rect"][3] <= y + h]
    big.sort(key=lambda e: e["rect"][0])
    i = DIALOG_CHOICES.index(want)
    return big[i] if len(big) == len(DIALOG_CHOICES) else None


def _panel(els: list[dict]) -> list[dict]:
    return [e for e in els if uia.visible(e) and e["rect"][0] < PANEL_MAX_X]


def pm_title(els: list[dict]) -> Optional[dict]:
    """The open PropertyManager's title, right above the row of square buttons: a wide named Button, or in the newer
    panels (Plane) a short Text."""
    squares = pm_squares(els)
    if not squares:
        return None
    above = [e for e in _panel(els) if _is_title(e, squares[0]["rect"][1])]
    return above[0] if above else None


def _is_title(e: dict, y: int) -> bool:
    wide_button = e.get("type") == "Button" and e["rect"][2] > 120
    label = e.get("type") == "Text" and e["rect"][1] < y
    return bool(e.get("name")) and (wide_button or label) and 0 <= y - (e["rect"][1] + e["rect"][3]) <= 12


def pm_squares(els: list[dict]) -> list[dict]:
    """The nameless square buttons in a row under the title (OK, Cancel, …), left to right."""
    sq = [e for e in _panel(els) if e.get("type") == "Button" and not e.get("name")
          and abs(e["rect"][2] - e["rect"][3]) <= 16 and 24 <= e["rect"][2] <= 60 and 24 <= e["rect"][3] <= 60]
    rows: dict[int, list[dict]] = {}
    for e in sq:
        rows.setdefault(e["rect"][1], []).append(e)
    for y in sorted(rows):
        row = sorted(rows[y], key=lambda e: e["rect"][0])
        if any(_is_title(e, y) for e in _panel(els)):
            return row
    return []


def pm_ok(els: list[dict]) -> Optional[dict]:
    """The green check. A panel still waiting for a selection has only the red cross, so one square isn't OK."""
    row = pm_squares(els)
    return row[0] if len(row) >= 2 else None


def pm_field(els: list[dict], where: Optional[str]) -> Optional[dict]:
    """The number field: the first Edit under the section `where` names ("Offset Entities PropertyManager,
    Parameters"; "Direction 1"), else the first one in the panel with a number in it."""
    panel = _panel(els)
    if pm_title(els) is None:
        return None
    edits = sorted((e for e in panel if e.get("type") == "Edit" and re.search(r"\d", e.get("value") or "")),
                   key=lambda e: e["rect"][1])
    words = [uia.norm(w).replace(" ", "") for w in (where or "").split(",")]
    for s in (e for e in panel if e.get("type") == "Button" and e.get("name")):
        if uia.norm(s["name"]).replace(" ", "") in words:
            below = [e for e in edits if e["rect"][1] > s["rect"][1]]
            if below:
                return below[0]
    return edits[0] if edits else None


class SolidWorksUIA(GenericUIA):
    def __init__(self, window: str = WINDOW, store=None, dump=None):
        super().__init__(window, store, dump or dump_all)

    def locate(self, step: Step, label: Optional[str] = None) -> tuple[Optional[Box], Optional[Line]]:
        t = step.target
        if label is None and t.kind not in uia.NOT_UIA:
            self.last_extra = {}
            els = self.dump(self.window)
            self.last_els, self.last_t = els, time.monotonic()
            el, how = None, ""
            if t.kind == "tree_item":
                el, how = tree_item(els, t.label), "tree row"
            elif t.kind == "field":
                el, how = pm_field(els, t.where), "PropertyManager field"
            elif OK_LABEL.match(t.label):
                el, how = pm_ok(els), "PropertyManager's green check"
            elif NEW_DIALOG.casefold() in (t.where or "").casefold():
                el, how = dialog_choice(els, t.label), "the New Document dialog"
            if el is not None:
                self.last_how = how
                return uia.box_of(el), None
            if t.kind == "tree_item":
                self.last_how = "no such row in the tree yet"
                return None, None
        return super().locate(step, label)
