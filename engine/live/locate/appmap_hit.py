"""Finder stage 4a: the box a control had the last time its step was checked done, from the local app map,
placed back into its window (positions are stored relative to the window, so moving it doesn't matter).

Only for controls that stay put: buttons and menu items. Editor lines, tabs and tree rows move as you work,
so they're never learned. A remembered box is a hint, not a fact: UIA beats it whenever UIA answers.
"""
from __future__ import annotations

from typing import Callable, Optional

from engine.schema.messages import Box
from engine.schema.tutorial import Step

LEARNABLE = {"button", "menu_item"}


def learnable(step: Step) -> bool:
    return step.target.kind in LEARNABLE and step.action in ("click", "menu_path")


def place(rel_box, win_rect) -> Box:
    rx, ry, rw, rh = rel_box
    wx, wy, ww, wh = win_rect
    return Box(x=round(wx + rx * ww), y=round(wy + ry * wh), w=max(1, round(rw * ww)), h=max(1, round(rh * wh)))


def remembered(step: Step, store, find_window: Callable[[str], Optional[tuple]]) -> Optional[Box]:
    """The learned box for this step's control, if there is one and its window is on screen.
    find_window(title part) → the window's (x, y, w, h), or None."""
    if store is None or not learnable(step):
        return None
    c = store.get(step.target.label)
    if c is None or c.seen is None:
        return None
    rect = find_window(c.seen.window)
    if rect is None:
        return None
    return place(c.seen.rel_box, rect)
