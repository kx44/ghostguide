"""Finder stage 4c: Spark vision. A screenshot of the app window, the target's label and `where`, and Spark
answers by calling our `point_at` tool with a box in screenshot pixels, which we map back to the screen.

**Off** unless FINDER_VISION=on: it's for apps without good accessibility data (SolidWorks' ribbon and canvas,
phase 4), and every call costs credits. Calls go through models/client.py, so MODEL_MODE (record / replay)
and the $4 budget cap apply; in replay mode an unrecorded request is simply a miss.
"""
from __future__ import annotations

from typing import Callable, Optional

from engine import config
from engine.models.tools import LOCATE_TOOLS, PointAt
from engine.schema.messages import Box
from engine.schema.tutorial import Step

# Spark's reasoning counts toward max_tokens, so leave room beyond the tool call.
MAX_TOKENS = 1024
EFFORT = "low"
PROMPT = ("This is a screenshot of {app}, {w} pixels wide and {h} pixels tall. Find the control for this tutorial step and call point_at with its box "
          "in screenshot pixels. If it isn't visible, call menu_path with the route to it, or not_found.\n"
          "Step: {title}\nControl: {label} ({kind})\nWhere: {where}")


def enabled() -> bool:
    return config.env("FINDER_VISION", "off").lower() in ("on", "1", "true", "yes")


def to_screen(p: PointAt, scale: float, origin: tuple[int, int]) -> Box:
    """Screenshot px (taken at `scale`, top-left at screen `origin`; p.x/p.y = center) → physical screen px box."""
    ox, oy = origin
    return Box(x=round(ox + (p.x - p.w / 2) / scale), y=round(oy + (p.y - p.h / 2) / scale),
               w=max(1, round(p.w / scale)), h=max(1, round(p.h / scale)))


class SparkVision:
    def __init__(self, app: str, client=None, grab: Optional[Callable[[], Optional[tuple]]] = None):
        self.app = app
        self.client = client
        self.grab = grab            # () → (png bytes, scale, origin) of the app window, or None
        self.last_how = ""

    def find(self, step: Step) -> Optional[Box]:
        if self.grab is None:
            self.last_how = "vision: no screenshot"
            return None
        shot = self.grab()
        if shot is None:
            self.last_how = "vision: window not visible"
            return None
        png, scale, origin = shot
        from engine.models.client import ModelClient, image_part, text_part
        c = self.client or ModelClient()
        t = step.target
        import io
        from PIL import Image
        w, h = Image.open(io.BytesIO(png)).size
        text = PROMPT.format(app=self.app, w=w, h=h, title=step.title, label=t.label, kind=t.kind, where=t.where or "-")
        try:
            reply = c.chat(model=config.SPARK, max_tokens=MAX_TOKENS, tools=LOCATE_TOOLS, reasoning_effort=EFFORT,
                           tag=f"find-step-{step.n}",
                           messages=[{"role": "user", "content": [text_part(text), image_part(png)]}])
        except Exception as e:      # replay miss, budget cap, network: a miss, never a crash
            self.last_how = f"vision: {e}"[:120]
            return None
        for call in reply.tool_calls:
            if isinstance(call, PointAt):
                self.last_how = f"vision: Spark pointed ({call.confidence})"
                return to_screen(call, scale, origin)
        self.last_how = "vision: Spark didn't point at it"
        return None
