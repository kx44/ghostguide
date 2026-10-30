"""Schema + rules (compile step 7). The overlay trusts the file blindly, so bad steps must stop here."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

from engine.basefile.parse import ParseError, parse_file
from engine.schema.tutorial import Tutorial

TIME_RE = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?(-\d{1,2}:\d{2}(:\d{2})?)?$")
# Keys that would mean a screen position slipped into the base file.
COORD_KEYS = {"x", "y", "box", "bbox", "rect", "rel_box", "coords", "coordinates", "position", "seen", "xy"}
MAX_STEPS = 500


@dataclass
class Report:
    name: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    steps: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors


def _coord_keys(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            here = f"{path}.{k}" if path else str(k)
            if str(k).lower() in COORD_KEYS:
                yield here
            yield from _coord_keys(v, here)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _coord_keys(v, f"{path}[{i}]")


def validate_tutorial(tut: Tutorial, name: str = "<tutorial>") -> Report:
    r = Report(name=name, steps=len(tut.steps))
    if not tut.steps:
        r.errors.append("no steps")
    if len(tut.steps) > MAX_STEPS:
        r.errors.append(f"{len(tut.steps)} steps (max {MAX_STEPS})")

    for i, s in enumerate(tut.steps, start=1):
        at = f"step {s.n}"
        if s.n != i:
            r.errors.append(f"{at}: steps must be numbered 1..N in order (expected {i})")
        if not s.title.strip():
            r.errors.append(f"{at}: empty title")
        if not s.check.strip():
            r.errors.append(f"{at}: empty check")
        if not s.target.label.strip():
            r.errors.append(f"{at}: empty target label")

        # Confidence or a repeat it inherits from
        if s.confidence is None and s.repeat_of is None:
            r.errors.append(f"{at}: needs confidence (or repeat_of)")

        # Repeats point back to an earlier, non-repeat step
        if s.repeat_of is not None:
            if not 1 <= s.repeat_of < s.n:
                r.errors.append(f"{at}: repeat_of {s.repeat_of} must point to an earlier step")
            else:
                orig = tut.step(s.repeat_of)
                if orig.repeat_of is not None:
                    r.errors.append(f"{at}: repeat_of {s.repeat_of}, which is itself a repeat; point at step {orig.repeat_of}")
                if orig.action != s.action:
                    r.warnings.append(f"{at}: repeat of step {orig.n} but action {s.action} ≠ {orig.action}")

        # Source
        if s.source.t and not TIME_RE.match(s.source.t):
            r.errors.append(f"{at}: source.t {s.source.t!r} is not mm:ss or mm:ss-mm:ss")
        if s.source.anchor and not s.source.anchor.startswith("#"):
            r.errors.append(f"{at}: source.anchor {s.source.anchor!r} must start with #")
        if tut.meta.source.type == "video" and not s.source.t:
            r.errors.append(f"{at}: video tutorial step needs source.t")

        # No coordinates anywhere in the step
        for key in _coord_keys(s.yaml_data()):
            r.errors.append(f"{at}: `{key}` looks like a screen position; describe targets by meaning")

        # Action-specific params
        p = s.params
        sug = p.get("suggested") if isinstance(p.get("suggested"), dict) else {}
        if s.action == "type" and "value" not in p and "value" not in sug:
            r.errors.append(f"{at}: type needs params.value (or params.suggested.value)")
        if s.action == "shortcut" and not (p.get("keys") or s.target.shortcut):
            r.errors.append(f"{at}: shortcut needs params.keys")
        if s.action == "menu_path" and not s.target.menu_path:
            r.warnings.append(f"{at}: menu_path step without target.menu_path (enrichment or Wonder must fill it)")
        if "click_type" in p and p["click_type"] not in ("right", "double", "middle", "ctrl", "shift", "alt"):
            r.errors.append(f"{at}: unknown click_type {p['click_type']!r}")

        if s.verify:
            for f in s.verify.file_checks():
                if Path(f.path).is_absolute() or ".." in Path(f.path).parts:
                    r.errors.append(f"{at}: verify.file path {f.path!r} must be relative to the working folder")
    return r


def validate_file(path: Union[str, Path]) -> Report:
    path = Path(path)
    try:
        tut = parse_file(path)
    except ParseError as e:
        return Report(name=path.name, errors=[str(e)])
    return validate_tutorial(tut, path.name)
