"""The start check (live step 2): the tutorial's `start_state`, as a checklist read from the real screen, shown
before step 1. Authors set up before recording; without this, step 1 fails for no fault of yours.

Only parts it can read get a tick or a cross ("SOLIDWORKS open", "no document"); the rest are listed for you to
look at. A cross holds the first step back until you press Start anyway, or until it comes true by itself; a
checklist with no crosses just goes straight to step 1. Pure, so it's tested off Windows.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

MAX_ITEMS = 6
MAX_TEXT = 90


def parts(start_state: Optional[str]) -> list[str]:
    """"SOLIDWORKS open, no document" → the two items. A paragraph (a long free-text state) isn't a checklist."""
    text = " ".join((start_state or "").split())
    if not text:
        return []
    items = [p.strip(" .") for p in re.split(r"[,;]", text) if p.strip(" .")]
    return [] if len(items) > MAX_ITEMS or any(len(i) > MAX_TEXT for i in items) else items


def evaluate(start_state: Optional[str], app: str, titles: list[str], document_open: Callable[[str], bool]) -> list[dict]:
    """[{text, ok}] with ok True / False, or None when it's yours to look at. `titles`: the app's top-level windows."""
    out = []
    for item in parts(start_state):
        low = item.casefold()
        ok: Optional[bool] = None
        if low.endswith(" open") and app.casefold() in low:
            ok = bool(titles)
        elif low == "no document":
            ok = bool(titles) and not any(document_open(t) for t in titles)
        out.append({"text": item, "ok": ok})
    return out


def holds_back(items: list[dict]) -> bool:
    return any(i["ok"] is False for i in items)
