"""AppMap: what we know about an app version's controls. Built-in layer = docs facts; local layer adds `seen`."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator


class Seen(BaseModel):
    """Where a control was last verified, relative to its window (0..1), so it survives moving the window."""
    model_config = ConfigDict(extra="forbid")
    window: str
    rel_box: tuple[float, float, float, float]   # x, y, w, h as fractions of the window
    look: Optional[list[int]] = None             # 8×8 grey thumbnail of the control, to tell it from its neighbours

    @field_validator("rel_box")
    @classmethod
    def _fractions(cls, v):
        if not all(0.0 <= f <= 1.0 for f in v):
            raise ValueError("rel_box values must be fractions of the window (0..1)")
        return v


class Control(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aliases: list[str] = Field(default_factory=list)   # names in other versions
    menu_path: Optional[list[str]] = None              # route when the button is hidden
    shortcut: Optional[str] = None
    source: Optional[str] = None                       # docs link the fact came from
    seen: Optional[Seen] = None                        # local layer only


class AppMap(RootModel[dict[str, Control]]):
    """`<app>-<version>.yaml`: control label → Control."""

    def get(self, label: str) -> Optional[Control]:
        if label in self.root:
            return self.root[label]
        for name, control in self.root.items():
            if label in control.aliases:
                return control
        return None

    @property
    def has_positions(self) -> bool:
        return any(c.seen for c in self.root.values())

    @classmethod
    def load(cls, path: Path) -> "AppMap":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls.model_validate(data)

    def dump(self, path: Path) -> None:
        data = self.model_dump(mode="json", exclude_none=True)
        Path(path).write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
