"""A second opinion on a box found by sight. Spark can box the control next door, and a click on it can spoil the rest of a
tutorial. The app's tooltip settles it for free, but only when the mouse is on the box, and in a flyout it usually isn't. So
a model looks at the box drawn on that part of the window: Glimmer, then Spark if Glimmer can't say.

It doesn't hold anything up for long: the answer comes in the background, and the finder keeps asking. Past WAIT_S (a cold
Glimmer takes up to a minute) the box is shown as it is, and goes away if a "no" comes later. Pure but for `_picture`'s PIL.
"""
from __future__ import annotations

import io
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from engine.schema.messages import Box
from engine.schema.tutorial import Step

WAIT_S = 15.0
PAD_X, PAD_Y = 240, 120     # around the box, window px
ZOOM = 2
MAX_LOOKS = 5               # per target, per run of a step
QUESTION = ("You check where an on-screen guide is pointing, in an enlarged part of a screenshot of {app}. A red rectangle "
            "marks where it points. It should be on this control: {label} ({kind}). Where the tutorial says it is: {where}.\n"
            "Answer with JSON only: {{\"result\": \"done\" | \"wrong\" | \"not_yet\", \"why\": \"<the name of what the red "
            "rectangle is on>\"}}. Say done only if the rectangle is on that control, going by its text or its icon; wrong if "
            "it's on a different control or on nothing; not_yet if you can't tell.")


def picture(img, origin: tuple[int, int], box: Box) -> bytes:
    """That part of the window, enlarged, with the box drawn on it."""
    from PIL import Image, ImageDraw

    x, y = box.x - origin[0], box.y - origin[1]
    x0, y0 = max(0, x - PAD_X), max(0, y - PAD_Y)
    x1, y1 = min(img.width, x + box.w + PAD_X), min(img.height, y + box.h + PAD_Y)
    part = img.crop((x0, y0, x1, y1)).convert("RGB")
    part = part.resize((part.width * ZOOM, part.height * ZOOM), Image.LANCZOS)
    at = [(x - x0) * ZOOM - 3, (y - y0) * ZOOM - 3, (x - x0 + box.w) * ZOOM + 3, (y - y0 + box.h) * ZOOM + 3]
    ImageDraw.Draw(part).rectangle(at, outline=(255, 0, 0), width=3)
    buf = io.BytesIO()
    part.save(buf, format="PNG")
    return buf.getvalue()


@dataclass
class _Look:
    t: float
    said: Optional[str] = None       # yes | no | unsure
    why: str = ""
    shown: bool = False              # asked for a step on screen, not ahead of it


class BoxCheck:
    def __init__(self, app: str, stages: list[Callable], grab: Callable[[], Optional[tuple]],
                 clock: Callable[[], float] = time.monotonic, start: Optional[Callable[[Callable[[], None]], None]] = None):
        self.app = app
        self.stages = [s for s in stages if s is not None]    # (step, png, text=, tag=) → Verdict
        self.grab = grab             # () → (PIL image, screen origin, scale), or None when it should stay on this PC
        self.clock = clock
        self.start = start or (lambda run: threading.Thread(target=run, daemon=True, name="box-check").start())
        self._looks: dict[tuple, _Look] = {}

    def forget(self, n: int) -> None:
        for k in [k for k, look in self._looks.items() if k[0] == n and look.shown]:
            del self._looks[k]

    def say(self, step: Step, label: str, box: Box, ahead: bool = False) -> tuple[str, str]:
        """(yes | no | wait | unsure, what it's on instead). "unsure" shows the box as it is. `ahead`: the step isn't showing
        yet, so the answer is waiting when it comes up."""
        key = (step.n, label, box.x, box.y, box.w, box.h)
        look = self._looks.get(key)
        if look is None:
            if not self.stages or sum(k[:2] == key[:2] for k in self._looks) >= MAX_LOOKS:
                return "unsure", ""
            shot = self.grab()
            if shot is None:
                return "unsure", ""
            look = self._looks[key] = _Look(self.clock())
            text = QUESTION.format(app=self.app, label=label, kind=step.target.kind, where=step.target.where or "-")
            png = picture(shot[0], shot[1], box)
            self.start(lambda: self._ask(step, png, text, look))
        look.shown = look.shown or not ahead
        if look.said is not None:
            return look.said, look.why
        return ("unsure" if self.clock() - look.t >= WAIT_S else "wait"), ""

    def _ask(self, step: Step, png: bytes, text: str, look: _Look) -> None:
        for stage in self.stages:
            try:
                v = stage(step, png, text=text, tag=f"box-step-{step.n}")
            except Exception:         # local-only, budget, network: the next one may answer, and no answer shows the box
                continue
            if v.result == "done":
                look.why, look.said = "", "yes"
                return
            if v.result == "wrong":
                look.why, look.said = v.why, "no"
                return
        look.said = "unsure"
