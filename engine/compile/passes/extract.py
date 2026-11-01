"""Pass 1: each segment → raw actions, with structured output, side by side (compile step 4)."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

from engine.compile.passes import CompileError, closed, prompt, read_json
from engine.compile.timeline import Evidence, Item, Segment, mmss
from engine.models.client import image_part, text_part

MAX_TOKENS = 24000      # reasoning counts toward this, and a long reasoning leaves an empty answer
EFFORT = "medium"
THIN_ACTIONS = 1        # this few from a part with this many pictures means the answer went wrong, not that nothing happened
THIN_IMAGES = 8
PARALLEL = 4
ACTIONS = ["click", "menu_path", "type", "shortcut", "draw_line", "drag", "pick", "switch_app", "wait", "look"]
KINDS = ["button", "tab", "menu_item", "field", "tree_item", "face", "edge", "canvas", "window"]
_S = {"type": "string"}
_L = {"type": "array", "items": _S}

SCHEMA = {
    "name": "raw_actions",
    "schema": closed({
        "type": "object",
        "properties": {
            "setup": _L,
            "actions": {"type": "array", "items": {
                "type": "object",
                "properties": {
                    "app": _S, "action": {"type": "string", "enum": ACTIONS}, "label": _S, "kind": {"type": "string", "enum": KINDS},
                    "where": _S, "value": _S, "then_key": _S, "keys": _L, "click_type": _S, "path": _L, "from": _S, "to": _S,
                    "direction": _S, "why": _S, "check": _S, "at": _S,
                    "evidence": {"type": "string", "enum": ["shown", "said", "implied"]}, "note": _S,
                },
                "required": ["action", "label", "kind", "at", "evidence"],
            }},
        },
        "required": ["actions"],
    }),
}


def _content(ev: Evidence, seg: Segment) -> list[dict]:
    head = f"Tutorial: {ev.title or 'untitled'}. Source: {ev.type}. Part {seg.n}."
    parts = [text_part(head)]
    if seg.context_image is not None:
        parts += [text_part(f"[screen just before this part, {mmss(seg.context_image.t or 0)}]"),
                  image_part(seg.context_image.image, "image/jpeg")]
    for item in seg.items:
        parts += _item(item)
    return parts


def _item(item: Item) -> list[dict]:
    if item.kind == "image":
        where = mmss(item.t) if item.t is not None else (item.anchor or "")
        alt = f" alt: {item.text}" if item.text else ""
        return [text_part(f"[picture, {where}]{alt}"), image_part(item.image, "image/jpeg")]
    if item.kind == "heading":
        return [text_part(f"\n## {item.text}  (anchor {item.anchor})")]
    if item.kind == "narration":
        span = f"{mmss(item.t)}-{mmss(item.end)}" if item.t is not None and item.end else mmss(item.t or 0)
        return [text_part(f"[{span}] {item.text}")]
    return [text_part(item.text)]


def extract_segment(client, model: str, ev: Evidence, seg: Segment) -> dict:
    messages = [{"role": "system", "content": prompt("extract")}, {"role": "user", "content": _content(ev, seg)}]
    fmt = {"type": "json_schema", "json_schema": SCHEMA}
    got = {}
    for effort in (EFFORT, "high"):      # a second, harder look at an answer that came back unreadable or nearly empty
        reply = client.chat(model=model, messages=messages, max_tokens=MAX_TOKENS, reasoning_effort=effort,
                            response_format=fmt, tag=f"compile-extract-{seg.n}", timeout=300)
        try:
            got = read_json(reply.text)
        except ValueError:
            got = {}
        if not isinstance(got, dict):     # a bare list, or nothing like the schema: the same as unreadable
            got = {}
        real = [a for a in got.get("actions") or [] if a.get("action") != "type" or a.get("value") or "suggested" in a.get("note", "")]
        if len(real) > THIN_ACTIONS or seg.images < THIN_IMAGES:
            break
    if not got:
        raise CompileError(f"Reading part {seg.n} gave an unreadable answer; try again.")
    return {"part": seg.n, "setup": got.get("setup") or [], "actions": got.get("actions") or []}


def extract(client, model: str, ev: Evidence, segments: list[Segment],
            done: Optional[Callable[[int, int], None]] = None) -> list[dict]:
    """Raw actions per segment, in order. A failed segment fails the compile rather than leaving a silent gap."""
    finished = 0
    results: list[Optional[dict]] = [None] * len(segments)

    def run(i: int) -> None:
        nonlocal finished
        results[i] = extract_segment(client, model, ev, segments[i])
        finished += 1
        if done:
            done(finished, len(segments))

    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        for f in [pool.submit(run, i) for i in range(len(segments))]:
            f.result()
    return results     # type: ignore[return-value]


def as_text(raw: list[dict]) -> str:
    return json.dumps(raw, ensure_ascii=False, indent=0)
