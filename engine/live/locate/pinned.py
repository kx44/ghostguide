"""Dev only (phase 2): hand-pinned target boxes, so the overlay can play a tutorial with no finder and no API.

Pins are physical screen pixels on one machine, so they never go in the base file and normally live in
`cache/pins/<tutorial>.yaml` (gitignored). Make them with `python -m engine pin <tutorial.md>`.

    screen: {w: 1920, h: 1080}          # info only: what the pins were taken on
    steps:
      1: {box: [x, y, w, h]}
      9: {same_as: 4}                   # reuse another step's pin
      20: {line: [[x1, y1], [x2, y2]]}  # draw_line / drag
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from engine import config
from engine.schema.messages import Box, Line


class Pin(BaseModel):
    model_config = ConfigDict(extra="forbid")
    box: Optional[tuple[int, int, int, int]] = None
    line: Optional[tuple[tuple[int, int], tuple[int, int]]] = None
    same_as: Optional[int] = None
    note: Optional[str] = None

    @model_validator(mode="after")
    def _one(self):
        if sum(v is not None for v in (self.box, self.line, self.same_as)) != 1:
            raise ValueError("a pin needs exactly one of box, line, same_as")
        if self.box and (self.box[2] <= 0 or self.box[3] <= 0):
            raise ValueError("box width and height must be positive")
        return self


class Pins(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tutorial: Optional[str] = None
    screen: Optional[dict] = None
    steps: dict[int, Pin] = Field(default_factory=dict)

    # ---------- lookups ----------
    def _resolve(self, n: int, seen: Optional[set] = None) -> Optional[Pin]:
        pin = self.steps.get(n)
        if pin is None or pin.same_as is None:
            return pin
        seen = seen or set()
        if n in seen:
            raise ValueError(f"pins: same_as loop at step {n}")
        seen.add(n)
        return self._resolve(pin.same_as, seen)

    def box(self, n: int) -> Optional[Box]:
        pin = self._resolve(n)
        if pin is None:
            return None
        if pin.box:
            x, y, w, h = pin.box
            return Box(x=x, y=y, w=w, h=h)
        if pin.line:
            (x1, y1), (x2, y2) = pin.line
            return Box(x=min(x1, x2), y=min(y1, y2), w=max(1, abs(x2 - x1)), h=max(1, abs(y2 - y1)))
        return None

    def line(self, n: int) -> Optional[Line]:
        pin = self._resolve(n)
        if pin is None or pin.line is None:
            return None
        return Line(start=pin.line[0], end=pin.line[1])

    # ---------- io ----------
    @classmethod
    def load(cls, path: Union[str, Path]) -> "Pins":
        path = Path(path)
        if not path.exists():
            return cls()
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls.model_validate(data)

    def dump(self, path: Union[str, Path]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.model_dump(mode="json", exclude_none=True)
        data["steps"] = {int(k): v for k, v in sorted(data.get("steps", {}).items(), key=lambda kv: int(kv[0]))}
        head = "# Hand-pinned target boxes (physical px) for dev playback. Made by `python -m engine pin`.\n"
        path.write_text(head + yaml.safe_dump(data, sort_keys=False, default_flow_style=None), encoding="utf-8")


def default_path(tutorial_path: Union[str, Path]) -> Path:
    return config.CACHE / "pins" / (Path(tutorial_path).stem + ".yaml")
