"""Finder stage 4d: when nothing on screen matches, the route to the control: the step's own `menu_path`, else
the app map's (docs facts), plus its shortcut. No box: the card carries the route as path chips, so you can
still get there. Muse Wonder with a fresh screenshot is the last resort for a route nobody knows; it arrives
with SolidWorks in phase 4 (it's the expensive model, and VS Code never needs it).
"""
from __future__ import annotations

from typing import Optional

from engine.schema.tutorial import Step


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


def describe(r: dict) -> str:
    bits = []
    if r.get("path"):
        bits.append(" › ".join(r["path"]))
    if r.get("shortcut"):
        bits.append(f"or {r['shortcut']}")
    return "Not on screen. Route: " + " ".join(bits)
