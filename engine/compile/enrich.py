"""Enrich: the app's official help → the local app map, for controls we know nothing about yet.

New entries only: what's already known, in either layer, is never searched for again or overwritten. Entries go to the
local layer unreviewed; only `engine appmap promote` moves them into the repo. A failed lookup never fails a compile,
because the live finder (Wonder) can still find the route.
"""
from __future__ import annotations

from typing import Optional

from engine.appmap.store import AppMapStore
from engine.compile.passes import prompt, read_json
from engine.models.client import BudgetExceeded, ModelError
from engine.schema.tutorial import Tutorial

BATCH = 15
MAX_OUTPUT = 6000
EFFORT = "low"
LOOKUP_KINDS = ("button", "menu_item", "tab")
LOOKUP_ACTIONS = ("click", "menu_path", "shortcut")


def new_controls(tut: Tutorial, store: AppMapStore) -> list[str]:
    """Labels worth looking up: named controls no layer of the app map has docs facts for."""
    out: list[str] = []
    for s in tut.steps:
        label = s.target.label.strip()
        if s.target.kind not in LOOKUP_KINDS or s.action not in LOOKUP_ACTIONS or label in out or label.casefold() in ("esc", "enter"):
            continue
        known = store.get(label)
        if known is None or not (known.aliases or known.menu_path or known.shortcut):
            out.append(label)
    return out


def _clean_entry(e: dict) -> Optional[dict]:
    if not isinstance(e, dict) or not e.get("label") or not str(e.get("source", "")).startswith("http"):
        return None      # a fact without a page behind it isn't a docs fact
    facts = {"source": e["source"]}
    if isinstance(e.get("menu_path"), list) and e["menu_path"]:
        facts["menu_path"] = [str(x) for x in e["menu_path"]]
    if isinstance(e.get("aliases"), list) and e["aliases"]:
        facts["aliases"] = [str(x) for x in e["aliases"] if str(x).casefold() != str(e["label"]).casefold()]
    if e.get("shortcut"):
        facts["shortcut"] = str(e["shortcut"])
    return facts if len(facts) > 1 else None


def enrich(client, model: str, tut: Tutorial, store: AppMapStore, version: Optional[str] = None, log=lambda s: None) -> dict:
    """Looks up new controls, saves them locally, fills the steps' route fields where they're empty."""
    labels = new_controls(tut, store)
    version_words = f", version {version}" if version else ""
    found: dict[str, dict] = {}
    searches = 0
    for i in range(0, len(labels), BATCH):
        batch = labels[i:i + BATCH]
        text = prompt("enrich").format(app=tut.meta.app, version_words=version_words, controls="\n".join(f"- {x}" for x in batch))
        try:
            reply = client.respond(model, text, max_output_tokens=MAX_OUTPUT, tools=[{"type": "web_search"}],
                                   reasoning_effort=EFFORT, tag=f"compile-enrich-{i // BATCH + 1}")
            answer = read_json(reply.text)
        except (ValueError, ModelError) as e:
            log(f"  enrich: batch {i // BATCH + 1} failed, the live finder will handle those ({e.__class__.__name__})")
            continue
        except BudgetExceeded:
            log("  enrich: stopped at the budget cap, the live finder will handle the rest")
            break
        searches += reply.searches
        for e in answer if isinstance(answer, list) else []:
            facts = _clean_entry(e)
            if facts and e["label"] in batch:
                found[e["label"]] = facts
    for label, facts in found.items():
        if store.get(label) is None or not (store.get(label).aliases or store.get(label).menu_path or store.get(label).shortcut):
            store.add_facts(label, **facts)
    for s in tut.steps:
        c = found.get(s.target.label.strip())
        if c:
            s.target.aliases = s.target.aliases or c.get("aliases")
            s.target.menu_path = s.target.menu_path or c.get("menu_path")
            s.target.shortcut = s.target.shortcut or c.get("shortcut")
    return {"asked": len(labels), "found": len(found), "searches": searches, "labels": sorted(found)}
