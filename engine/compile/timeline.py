"""The evidence timeline (compile step 3): what every adapter ends up as, cut into segments for pass 1.

An item is narration, text, a heading or an image, in reading order. Images stay beside the words around them, because
narration alone got things wrong and frames fixed them. Segments keep each model call under Meta's image limit, and
video cuts fall where the narrator pauses, so an action isn't split in the middle when it can be helped.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from engine import config

Kind = Literal["heading", "text", "narration", "image"]

MAX_IMAGES = 40           # per segment; a segment may run over to reach a pause, never past HARD_MAX_IMAGES
HARD_MAX_IMAGES = config.MAX_IMAGES - 2
MAX_SPAN_S = 90           # video: start looking for a pause after this long
MAX_CHARS = 16000         # text: start a new segment at the next heading after this much


@dataclass
class Item:
    kind: Kind
    text: str = ""                     # words, or an image's alt text
    t: Optional[float] = None          # seconds in the original video
    end: Optional[float] = None
    anchor: Optional[str] = None       # "#section" (web, text)
    image: Optional[bytes] = None      # JPEG

    def to_wire(self, name: Optional[str] = None) -> dict:
        d = {"kind": self.kind, "text": self.text, "t": self.t, "end": self.end, "anchor": self.anchor}
        if name:
            d["image"] = name
        return d


@dataclass
class Evidence:
    type: Literal["video", "web", "text"]
    hash: str
    items: list[Item]
    url: Optional[str] = None
    title: Optional[str] = None
    author: Optional[str] = None
    published: Optional[str] = None
    segment: Optional[str] = None      # "01:28-10:25": the part of a video asked for
    notes: list[str] = field(default_factory=list)

    @property
    def images(self) -> int:
        return sum(1 for i in self.items if i.kind == "image")


@dataclass
class Segment:
    n: int
    items: list[Item]
    context_image: Optional[Item] = None    # the last image before this segment: the screen as it starts

    @property
    def images(self) -> int:
        return sum(1 for i in self.items if i.kind == "image") + (self.context_image is not None)


def mmss(t: float) -> str:
    t = int(t)
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60:02d}:{t % 60:02d}"


def cut_video(items: list[Item], max_images: int = MAX_IMAGES, max_span_s: float = MAX_SPAN_S) -> list[list[Item]]:
    """In time order, cutting at the start of a narration turn once a segment is long enough."""
    out, cur, images, start = [], [], 0, None
    for item in items:
        if start is None and item.t is not None:
            start = item.t
        long_enough = images >= max_images or (start is not None and item.t is not None and item.t - start >= max_span_s)
        if cur and ((long_enough and item.kind == "narration") or (item.kind == "image" and images >= HARD_MAX_IMAGES)):
            out.append(cur)
            cur, images, start = [], 0, item.t
        cur.append(item)
        images += item.kind == "image"
    if cur:
        out.append(cur)
    return out


def cut_text(items: list[Item], max_images: int = MAX_IMAGES, max_chars: int = MAX_CHARS) -> list[list[Item]]:
    """In reading order, cutting at a heading once a segment is long enough."""
    out, cur, images, chars = [], [], 0, 0
    for item in items:
        full = images >= max_images or chars >= max_chars
        if cur and ((full and item.kind == "heading") or (item.kind == "image" and images >= HARD_MAX_IMAGES)
                    or chars >= max_chars * 2):
            out.append(cur)
            cur, images, chars = [], 0, 0
        cur.append(item)
        images += item.kind == "image"
        chars += len(item.text)
    if cur:
        out.append(cur)
    return out


def segments(ev: Evidence, max_images: int = MAX_IMAGES) -> list[Segment]:
    if ev.type == "video":
        items = sorted(ev.items, key=lambda i: (i.t if i.t is not None else 0.0, i.kind != "narration"))
        parts = cut_video(items, max_images)
    else:
        parts = cut_text(ev.items, max_images)
    out, last_image = [], None
    for n, part in enumerate(parts, start=1):
        out.append(Segment(n=n, items=part, context_image=last_image if ev.type == "video" else None))
        last_image = next((i for i in reversed(part) if i.kind == "image"), last_image)
    return out
