"""The UI Automation stage of the finder (live step 4b), and the UIA dump every check reads.

Finding: an app with its own rule pack (VS Code: locate/vscode.py, where labels alone fail) uses it; any
other app is searched by the target's label and the app map's aliases, among the control types its kind
allows, in its own window only. Names are compared whole, with key hints like "(Ctrl+S)" stripped, so
"Save" doesn't match "Save to playlist" in another window (phase 1's false hits).

The matching is pure over dumped element dicts, so it's tested off Windows.
"""
from __future__ import annotations

import re
import time
from typing import Iterable, Optional

from engine.schema.messages import Box

_HINTS = re.compile(r"\s*(\[alt\].*|\((ctrl|alt|shift|win|f\d+)[^)]*\))\s*$", re.I)

KIND_TYPES = {
    "button": ("Button", "SplitButton", "MenuItem", "ListItem", "CheckBox", "RadioButton", "TabItem", "Hyperlink"),
    "tab": ("TabItem",),
    "menu_item": ("MenuItem", "Button", "ListItem"),
    "field": ("Edit", "ComboBox", "Document", "Spinner"),
    "tree_item": ("TreeItem", "ListItem", "DataItem"),
    "window": ("Window", "Pane"),
}
NOT_UIA = {"canvas", "face", "edge"}       # drawn, not controls: vision's job


def norm(s: Optional[str]) -> str:
    s = " ".join((s or "").replace("…", "...").split()).casefold()
    prev = None
    while prev != s:
        prev, s = s, _HINTS.sub("", s)
    return s


def visible(el: dict) -> bool:
    r = el.get("rect")
    return bool(r) and r[2] > 0 and r[3] > 0 and not el.get("offscreen", False)


def find_named(els: Iterable[dict], names: list[str], kind: str) -> Optional[dict]:
    """First visible element whose name is one of `names` (label first, then aliases), preferring the
    control types the kind allows over any other type."""
    wanted = [norm(n) for n in names if n]
    types = KIND_TYPES.get(kind, ())
    best = None
    for el in els:
        if not visible(el):
            continue
        name = norm(el.get("name"))
        if name not in wanted:
            continue
        score = (len(wanted) - wanted.index(name)) * 2 + (1 if el.get("type") in types else 0)
        if best is None or score > best[0]:
            best = (score, el)
    return best[1] if best else None


def box_of(el: dict) -> Box:
    x, y, w, h = el["rect"]
    return Box(x=int(x), y=int(y), w=int(w), h=int(h))


# ---------- Windows layer -----------------------------------------------------------------------
def dump(window: str, max_depth: int = 60, max_elements: int = 6000, tries: int = 3, every: bool = False) -> list[dict]:
    """UIA elements of the top-level window whose title contains `window` (all such windows with
    `every`, e.g. each Chrome window). Each element carries its window's title. The walk can throw when
    the UI changes under it (a menu closing, the app starting), so it retries."""
    for i in range(tries):
        try:
            return _dump(window, max_depth, max_elements, every)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(0.2)
    return []


def _dump(window: str, max_depth: int, max_elements: int, every: bool) -> list[dict]:
    import uiautomation as auto

    from engine.live.windows import foreign_browser

    out: list[dict] = []
    for top in auto.GetRootControl().GetChildren():
        title = top.Name or ""
        if window.casefold() not in title.casefold() or foreign_browser(title, window):
            continue
        for ctrl, _ in auto.WalkControl(top, includeTop=True, maxDepth=max_depth):
            if len(out) >= max_elements:
                break
            try:
                r = ctrl.BoundingRectangle
                t = ctrl.ControlTypeName.removesuffix("Control")
                el = {"name": ctrl.Name, "type": t, "rect": [r.left, r.top, r.width(), r.height()],
                      "offscreen": bool(ctrl.IsOffscreen), "window": title}
                if t == "Edit":
                    vp = ctrl.GetPattern(auto.PatternId.ValuePattern)
                    if vp:
                        el["value"] = vp.Value
                elif t == "TabItem":
                    sp = ctrl.GetPattern(auto.PatternId.SelectionItemPattern)
                    if sp:
                        el["selected"] = bool(sp.IsSelected)
            except Exception:   # elements vanish mid-walk; keep going
                continue
            out.append(el)
        if not every:
            break
    return out
