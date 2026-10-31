"""Pass 2: raw actions → the whole tutorial, with `verify` hints (compile step 5). A draft that fails validation goes
back once with the errors listed, then the compile stops and says why (compile step 7)."""
from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from engine.basefile.validate import validate_tutorial
from engine.compile.passes import CompileError, closed, prompt, read_json
from engine.compile.passes.extract import ACTIONS, KINDS, as_text
from engine.compile.timeline import Evidence
from engine.schema.tutorial import Step, Tutorial, TutorialMeta

MAX_TOKENS = 32000
EFFORT = "high"     # the whole-tutorial view is where steps get inferred; this pass has no images, so thinking is cheap
_S = {"type": "string"}
_L = {"type": "array", "items": _S}
_UIA = {"type": "object", "properties": {
    "name": _S, "name_contains": _S, "type": _S, "value_contains": _S, "window": _S, "selected": {"type": "boolean"},
    "exists": {"type": "boolean"}}}
_FILE = {"type": "object", "properties": {"path": _S, "contains": _S}, "required": ["path"]}

SCHEMA = {
    "name": "tutorial",
    "schema": closed({
        "type": "object",
        "properties": {
            "title": _S, "app": _S, "author_version": _S, "start_state": _S, "units": _S,
            "steps": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "title": _S, "part": _S,
                    "action": {"type": "string", "enum": ACTIONS},
                    "target": {"type": "object", "properties": {
                        "label": _S, "kind": {"type": "string", "enum": KINDS}, "where": _S, "menu_path": _L, "shortcut": _S},
                        "required": ["label", "kind"]},
                    "params": {"type": "object", "properties": {
                        "value": _S, "then_key": _S, "keys": _L, "click_type": _S, "from": _S, "to": _S, "direction": _S,
                        "length": _S, "field": _S,
                        "suggested": {"type": "object", "properties": {"value": _S, "note": _S}}}},
                    "why": _S, "check": _S,
                    "verify": {"type": "object", "properties": {"uia": {"type": "array", "items": _UIA},
                                                                 "file": {"type": "array", "items": _FILE}}},
                    "source": {"type": "object", "properties": {"t": _S, "anchor": _S}},
                    "confidence": {"type": "string", "enum": ["high", "low", "inferred"]},
                    "repeat_of": {"type": "integer"}, "optional": {"type": "boolean"},
                },
                "required": ["title", "action", "target", "check", "source", "confidence"],
            }},
        },
        "required": ["title", "app", "steps"],
    }),
}


def _clean(obj: Any) -> Any:
    """Empty fields out, so an unset optional reads as unset."""
    if isinstance(obj, dict):
        out = {k: _clean(v) for k, v in obj.items()}
        return {k: v for k, v in out.items() if v not in (None, "", [], {})}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    return obj


def to_tutorial(data: dict, ev: Evidence) -> tuple[Tutorial, list[str]]:
    """The draft as a Tutorial, and what's wrong with it: bad steps are reported, never dropped quietly."""
    errors: list[str] = []
    steps: list[Step] = []
    raw_steps = data.get("steps") or []
    for n, raw in enumerate(raw_steps, start=1):
        raw = _clean(raw)
        v = raw.get("verify")
        if v:      # a one-item list reads better in the file, and validates the same
            for k in ("uia", "file"):
                if isinstance(v.get(k), list) and len(v[k]) == 1:
                    v[k] = v[k][0]
        fields = {k: raw[k] for k in raw if k not in ("title", "part")}
        try:
            steps.append(Step(n=n, title=raw.get("title", ""), part=raw.get("part"), **fields))
        except (ValidationError, TypeError) as e:
            detail = "; ".join(f"{'.'.join(str(x) for x in er['loc'])}: {er['msg']}" for er in e.errors()) if isinstance(e, ValidationError) else str(e)
            errors.append(f"step {n}: {detail}")
    source = {"type": ev.type, "url": ev.url, "hash": ev.hash}
    for k in ("author", "published", "segment"):
        if getattr(ev, k):
            source[k] = getattr(ev, k)
    meta = TutorialMeta(title=data.get("title") or ev.title or "Untitled", app=data.get("app") or "Unknown",
                        author_version=data.get("author_version"), source=source, start_state=data.get("start_state"),
                        units=data.get("units"))
    tut = Tutorial(meta=meta, steps=steps)
    if not errors:
        errors = validate_tutorial(tut).errors
    return tut, errors


def _source_lines(ev: Evidence) -> str:
    lines = [f"Source: {ev.type}", f"Title: {ev.title or 'unknown'}"]
    if ev.published:
        lines.append(f"Published: {ev.published}")
    if ev.segment:
        lines.append(f"Only this part of the video is the tutorial: {ev.segment}")
    anchors = [i.anchor for i in ev.items if i.kind == "heading"]
    if anchors:
        lines.append("Anchors: " + ", ".join(anchors))
    return "\n".join(lines)


def merge(client, model: str, ev: Evidence, raw: list[dict]) -> Tutorial:
    fmt = {"type": "json_schema", "json_schema": SCHEMA}
    messages = [{"role": "system", "content": prompt("merge")},
                {"role": "user", "content": f"{_source_lines(ev)}\n\nRaw actions:\n{as_text(raw)}"}]
    reply = client.chat(model=model, messages=messages, max_tokens=MAX_TOKENS, reasoning_effort=EFFORT, response_format=fmt,
                        tag="compile-merge", timeout=600)
    errors = ["the answer wasn't valid JSON"]
    try:
        tut, errors = to_tutorial(read_json(reply.text), ev)
    except ValueError:
        tut = None
    if not errors:
        return tut
    messages += [{"role": "assistant", "content": reply.text or "{}"},
                 {"role": "user", "content": "That draft has these problems. Send the whole tutorial again with them fixed:\n- "
                                             + "\n- ".join(errors[:40])}]
    reply = client.chat(model=model, messages=messages, max_tokens=MAX_TOKENS, reasoning_effort=EFFORT, response_format=fmt,
                        tag="compile-merge-retry", timeout=600)
    try:
        tut, errors = to_tutorial(read_json(reply.text), ev)
    except ValueError as e:
        raise CompileError("Writing the steps gave an unreadable answer twice.") from e
    if errors:
        raise CompileError("The compiled steps don't pass the checks:\n  " + "\n  ".join(errors[:12]))
    return tut


def dumps_draft(tut: Tutorial) -> str:
    return json.dumps([s.yaml_data() | {"title": s.title} for s in tut.steps], ensure_ascii=False, indent=1)
