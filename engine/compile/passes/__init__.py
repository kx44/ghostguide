"""The two model passes (compile steps 4 and 5). Prompts live in prompts/ as plain text, so they can be read and diffed."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

PROMPTS = Path(__file__).parent / "prompts"


class CompileError(RuntimeError):
    """The compile can't go on. The message is written for the person importing."""


def prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


def prompts_version() -> str:
    """Changes when any prompt does, so a tuned prompt recompiles and an unchanged one reuses its result."""
    h = hashlib.sha256()
    for p in sorted(PROMPTS.glob("*.md")):
        h.update(p.read_bytes())
    return h.hexdigest()[:12]


def closed(schema: Any) -> Any:
    """Every object in a schema takes only the keys it lists. Without this the model can invent keys ("params': {"
    came back once), which reads as the field being missing."""
    if isinstance(schema, dict):
        out = {k: closed(v) for k, v in schema.items()}
        if out.get("type") == "object":
            out["additionalProperties"] = False
        return out
    if isinstance(schema, list):
        return [closed(v) for v in schema]
    return schema


def read_json(text: str) -> Any:
    """The model's reply as data. Structured output is plain JSON; a web-search answer may wrap it in a code fence."""
    t = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if fence:
        t = fence.group(1).strip()
    try:
        return json.loads(t)
    except ValueError:
        start = min((i for i in (t.find("["), t.find("{")) if i >= 0), default=-1)
        end = max(t.rfind("]"), t.rfind("}"))
        if start < 0 or end <= start:
            raise
        return json.loads(t[start:end + 1])
