"""Explain pass: a plain-words `why` for the steps that have none, so a person following along understands what they type.

It only ever fills empty `why` fields. The reply is read as (step number, line) pairs and nothing else in it is looked
at, and the steps are compared before and after. A failed pass never fails a compile: the steps save without the lines.
"""
from __future__ import annotations

import json
import re

from engine.compile.passes import closed, prompt, read_json
from engine.schema.tutorial import Step, Tutorial

MAX_TOKENS = 8000       # reasoning counts toward this
EFFORT = "low"
MAX_WORDS, MAX_CHARS = 24, 160              # "about 20 words", with a little give so a good line isn't thrown away
LONG_MAX_WORDS, LONG_MAX_CHARS = 34, 220    # two short lines, for a long block of typed text
LONG_BLOCK_CHARS, LONG_BLOCK_LINES = 200, 4
_S = {"type": "string"}

SCHEMA = {
    "name": "explanations",
    "schema": closed({
        "type": "object",
        "properties": {
            "explanations": {"type": "array", "items": {
                "type": "object",
                "properties": {"n": {"type": "integer"}, "why": _S},
                "required": ["n", "why"],
            }},
        },
        "required": ["explanations"],
    }),
}


def _typed(step: Step) -> str:
    value = step.params.get("value")
    suggested = step.params.get("suggested")
    if value is None and isinstance(suggested, dict):
        value = suggested.get("value")
    return "" if value is None else str(value)


def _is_long(step: Step) -> bool:
    text = _typed(step)
    return len(text) >= LONG_BLOCK_CHARS or text.count("\n") + 1 >= LONG_BLOCK_LINES


def _empty(step: Step) -> bool:
    return not (step.why or "").strip()


def _open_steps(tut: Tutorial) -> tuple[set[int], set[int]]:
    """Step numbers that must get a line (typed text) and that may (the rest; a repeat's small card doesn't show one)."""
    must = {s.n for s in tut.steps if _empty(s) and s.action == "type"}
    may = {s.n for s in tut.steps if _empty(s) and s.action != "type" and s.repeat_of is None}
    return must, may


def _frozen(tut: Tutorial) -> list[dict]:
    """Everything about the steps except `why`."""
    return [{"n": s.n, "title": s.title, "part": s.part, **{k: v for k, v in s.yaml_data().items() if k != "why"}} for s in tut.steps]


def _brief(tut: Tutorial, must: set[int], may: set[int]) -> str:
    rows = []
    for s in tut.steps:
        row = {"n": s.n, "title": s.title, "action": s.action, "target": s.target.label, "where": s.target.where}
        if s.action == "type":
            row["text"] = _typed(s)
            if "value" not in s.params:
                row["suggested_by_us"] = True
        row["done_when"] = s.check
        if s.why:
            row["why"] = s.why
        row["explain"] = "required" if s.n in must else "optional" if s.n in may else "no"
        rows.append({k: v for k, v in row.items() if v is not None})
    return (f"Tutorial: {tut.meta.title}\nApp: {tut.meta.app}\n\nSteps:\n" + json.dumps(rows, ensure_ascii=False, indent=0))


def _words(text: str) -> str:
    return re.sub(r"\W+", " ", text.casefold()).strip()


def _problem(line: str, step: Step) -> str | None:
    """Why this line can't go on the card, or None. Too long is refused rather than cut: half a sentence explains nothing."""
    words, chars = (LONG_MAX_WORDS, LONG_MAX_CHARS) if _is_long(step) else (MAX_WORDS, MAX_CHARS)
    if not line:
        return "is empty"
    if len(line.split()) > words or len(line) > chars:
        return f"is too long ({len(line.split())} words; at most {words} words and {chars} characters)"
    if _words(line) in (_words(step.title), _words(step.check)):
        return "only repeats the step"
    return None


def _read(text: str, tut: Tutorial, allowed: set[int]) -> tuple[dict[int, str], dict[int, str]]:
    """Good lines and refused ones, by step number, from the reply. Only `n` and `why` are ever read."""
    answer = read_json(text)
    entries = answer.get("explanations") if isinstance(answer, dict) else None
    if not isinstance(entries, list):
        raise ValueError("no explanations list")
    good: dict[int, str] = {}
    bad: dict[int, str] = {}
    for e in entries:
        n, why = e.get("n") if isinstance(e, dict) else None, e.get("why") if isinstance(e, dict) else None
        if type(n) is not int or n not in allowed or not isinstance(why, str) or n in good:
            continue
        line = " ".join(why.split())
        problem = _problem(line, tut.step(n))
        if problem:
            bad[n] = problem
        else:
            good[n] = line
    return good, bad


def fill(tut: Tutorial, lines: dict[int, str]) -> set[int]:
    """The only place this pass writes to a step, and only to an empty `why`. Returns the steps it wrote to."""
    filled = set()
    for s in tut.steps:
        if _empty(s) and s.n in lines:
            s.why = lines[s.n]
            filled.add(s.n)
    return filled


def explain(client, model: str, tut: Tutorial, log=lambda s: None) -> dict:
    """Fills empty `why` fields in place. Never raises: what went wrong comes back as `warnings`."""
    must, may = _open_steps(tut)
    info = {"asked": len(must), "filled": 0, "filled_optional": 0, "warnings": []}
    if not must and not may:
        return info
    frozen = _frozen(tut)
    fmt = {"type": "json_schema", "json_schema": SCHEMA}
    messages = [{"role": "system", "content": prompt("explain")}, {"role": "user", "content": _brief(tut, must, may)}]
    good: dict[int, str] = {}
    try:
        for tag in ("compile-explain", "compile-explain-retry"):
            reply = client.chat(model=model, messages=messages, max_tokens=MAX_TOKENS, reasoning_effort=EFFORT, response_format=fmt,
                                tag=tag, timeout=180)
            refused: dict[int, str] = {}
            unreadable = False
            try:
                new, refused = _read(reply.text, tut, (must | may) - set(good))
                good.update(new)
            except (ValueError, AttributeError):
                unreadable = True
            missing = sorted(must - set(good))
            if not unreadable and not missing:
                break
            ask = ["That answer wasn't valid JSON."] if unreadable else []
            ask += [f"Step {n}: the line {refused[n]}." for n in sorted(refused)]
            ask += [f"Step {n}: it needs a line." for n in missing if n not in refused]
            messages = messages[:2] + [{"role": "assistant", "content": reply.text or "{}"},
                                       {"role": "user", "content": "Send only these steps again, fixed:\n- " + "\n- ".join(ask)}]
    except Exception as e:      # anything at all: the steps are good, and they save without the lines
        info["warnings"].append(f"Explanations stopped early ({e.__class__.__name__}: {str(e)[:160]}).")
        log(f"  explain: {info['warnings'][-1]}")

    filled = fill(tut, good)
    if _frozen(tut) != frozen:    # can't happen by the code above; if it ever does, the lines go and the steps stand
        for s in tut.steps:
            if s.n in filled:
                s.why = None
        info["warnings"].append("Explanations dropped: they would have changed a step.")
        good = {}
    info["filled"] = len(must & set(good))
    info["filled_optional"] = len(may & set(good))
    missing = sorted(must - set(good))
    if missing:
        info["warnings"].append("No explanation for typed step" + ("s " if len(missing) > 1 else " ") + ", ".join(map(str, missing)) + ".")
    return info
