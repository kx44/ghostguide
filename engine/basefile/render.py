"""Tutorial → .md. Unchanged steps and frontmatter are written back exactly as read (comments kept)."""
from __future__ import annotations

from pathlib import Path
from typing import Union

import yaml

from engine.schema.tutorial import Step, Tutorial


class _Dumper(yaml.SafeDumper):
    pass


def _str(dumper, value: str):
    style = "|" if "\n" in value else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", value, style=style)


_Dumper.add_representer(str, _str)


def _dump(data) -> str:
    return yaml.dump(data, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=110)


def _meta_data(tut: Tutorial) -> dict:
    return tut.meta.model_dump(mode="json", exclude_none=True, exclude_defaults=False)


def _frontmatter(tut: Tutorial) -> str:
    raw, raw_data = tut._raw_frontmatter, tut._raw_meta
    if raw is not None and raw_data is not None:
        # Same content as read (ignoring defaults the file left out) → keep the original text.
        if tut.meta.model_validate(raw_data) == tut.meta:
            return raw
    data = _meta_data(tut)
    if not data.get("gold"):
        data.pop("gold", None)
    return _dump(data)


def _step_yaml(step: Step) -> str:
    data = step.yaml_data()
    if step._raw is not None and step._raw_data is not None:
        reread = Step.model_validate({**step._raw_data, "n": step.n, "title": step.title})
        if reread.yaml_data() == data:
            return step._raw
    return _dump(data)


def render_text(tut: Tutorial) -> str:
    out = ["---\n", _frontmatter(tut), "---\n"]
    part = None
    for step in tut.steps:
        if step.part and step.part != part:
            out.append(f"\n# {step.part}\n\n")
            part = step.part
        out.append(f"## Step {step.n} — {step.title}\n```yaml\n{_step_yaml(step)}```\n")
    return "".join(out)


def render_file(tut: Tutorial, path: Union[str, Path]) -> None:
    Path(path).write_text(render_text(tut), encoding="utf-8", newline="\n")
