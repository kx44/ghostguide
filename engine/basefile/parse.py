""".md → Tutorial. Layout: YAML frontmatter, optional `# Part …` headings, `## Step N — title` + one ```yaml block each."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Union

import yaml
from pydantic import ValidationError

from engine.schema.tutorial import Step, Tutorial, TutorialMeta

STEP_RE = re.compile(r"^## Step (\d+)\s+[—-]\s+(.+?)\s*$")
PART_RE = re.compile(r"^# (.+?)\s*$")


class ParseError(ValueError):
    def __init__(self, where: str, message: str):
        super().__init__(f"{where}: {message}")
        self.where = where
        self.message = message


def _split_frontmatter(text: str, name: str) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise ParseError(name, "missing YAML frontmatter (file must start with ---)")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ParseError(name, "frontmatter is not closed with ---")
    return text[4:end + 1], text[end + 5:]


def parse_text(text: str, name: str = "<text>") -> Tutorial:
    text = text.replace("\r\n", "\n")
    fm_raw, body = _split_frontmatter(text, name)
    try:
        fm_data = yaml.safe_load(fm_raw) or {}
        meta = TutorialMeta.model_validate(fm_data)
    except (yaml.YAMLError, ValidationError) as e:
        raise ParseError(f"{name} frontmatter", str(e)) from e

    steps: list[Step] = []
    part = None
    heading = None          # (n, title, line no) of the step whose YAML block we expect next
    lines = body.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        if m := STEP_RE.match(line):
            if heading:
                raise ParseError(f"{name} step {heading[0]}", "heading has no ```yaml block")
            heading = (int(m.group(1)), m.group(2), i)
        elif m := PART_RE.match(line):
            if heading:
                raise ParseError(f"{name} step {heading[0]}", "heading has no ```yaml block")
            part = m.group(1)
        elif line.strip() == "```yaml":
            if not heading:
                raise ParseError(f"{name} body line {i + 1}", "```yaml block without a `## Step N — title` heading")
            j = i + 1
            while j < len(lines) and lines[j].strip() != "```":
                j += 1
            if j == len(lines):
                raise ParseError(f"{name} step {heading[0]}", "```yaml block is not closed")
            raw = "\n".join(lines[i + 1:j]) + "\n"
            steps.append(_step(raw, heading, part, name))
            heading = None
            i = j
        elif line.strip() and not line.startswith("---"):
            # Prose outside blocks isn't part of the format; refuse rather than lose it on render.
            raise ParseError(f"{name} body line {i + 1}", f"unexpected text: {line[:60]!r}")
        i += 1
    if heading:
        raise ParseError(f"{name} step {heading[0]}", "heading has no ```yaml block")

    tut = Tutorial(meta=meta, steps=steps)
    tut._raw_frontmatter = fm_raw
    tut._raw_meta = fm_data
    return tut


def _step(raw: str, heading: tuple, part, name: str) -> Step:
    n, title, _ = heading
    where = f"{name} step {n}"
    try:
        data = yaml.safe_load(raw) or {}
    except yaml.YAMLError as e:
        raise ParseError(where, f"bad YAML: {e}") from e
    if not isinstance(data, dict):
        raise ParseError(where, "YAML block must be a mapping")
    try:
        step = Step.model_validate({**data, "n": n, "title": title, "part": part})
    except ValidationError as e:
        msgs = "; ".join(f"{'.'.join(map(str, err['loc'])) or 'step'}: {err['msg']}" for err in e.errors())
        raise ParseError(where, msgs) from e
    step._raw = raw
    step._raw_data = data
    return step


def parse_file(path: Union[str, Path]) -> Tutorial:
    path = Path(path)
    return parse_text(path.read_text(encoding="utf-8"), name=path.name)
