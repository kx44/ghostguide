"""Card check (Windows): are the cards of a tutorial readable and clear of their targets, on the real overlay and VS Code?

    py -m tests.accuracy.card_check --tutorial tutorials/compiled/youtube-clone-vscode.compiled.md

overlay_check's walk is tied to the gold file's step numbers (hide at 12, restart at 17), so this one takes any VS Code
tutorial and only looks at the cards. For each step: the card's height, whether it's inside the screen, whether it covers
the target or the lines the code goes on, and whether the step's `why` is on it. Steps move on by the hotkey, with the
engine's own checks off. Takes the mouse and keyboard for about 3 minutes. Results: cache/screenshots/card-check/.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from engine import config
from engine.basefile.parse import parse_file
from engine.live.locate.vscode import VSCodeLocator
from engine.schema.messages import Box
from tests.accuracy.landing_walk import FOLDER, TUTORIAL, act, bring_front, prepare, setup, top_window
from tests.accuracy.overlay_check import (OVERLAY, _intersects, card_rect, find, grab, hotkey, kill, ov_elements, start_engine,
                                          start_overlay, wait_step)

OUT = config.CACHE / "screenshots" / "card-check"


def card_row(step, guide: dict, els: list[dict], screen: tuple[int, int]) -> dict:
    """What the check says about one step's card (physical px). Plain data in, plain data out."""
    row: dict = {"n": step.n, "title": step.title, "style": guide["style"]}
    c = card_rect(els, guide)
    if not c:
        return {**row, "card": None}
    box = guide.get("box")
    avoid = (guide.get("extra") or {}).get("avoid") or []
    row.update(card=c, height=c[3], top=c[1], bottom=c[1] + c[3],
               on_screen=c[0] >= 0 and c[1] >= 0 and c[0] + c[2] <= screen[0] and c[1] + c[3] <= screen[1],
               covers_target=bool(box) and _intersects(c, [box["x"], box["y"], box["w"], box["h"]]),
               covers_work=any(_intersects(c, [a["x"], a["y"], a["w"], a["h"]]) for a in avoid))
    if step.why:
        row["why_shown"] = any(e["name"] == step.why for e in els)
    return row


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tutorial", default=str(TUTORIAL))
    ap.add_argument("--to", type=int, default=None, help="stop after this step")
    args = ap.parse_args(argv)
    if sys.platform != "win32":
        print("Needs Windows.")
        return 2
    from engine.dpi import make_dpi_aware
    make_dpi_aware()
    tutorial = Path(args.tutorial).resolve()
    tut = parse_file(tutorial)
    OUT.mkdir(parents=True, exist_ok=True)

    win, title = setup(FOLDER, fresh=True)
    eng, rec = start_engine(restart=True, tag="cards", tutorial=tutorial, extra=("--check", "off"))
    ov = start_overlay()
    rows: list[dict] = []
    try:
        rec.wait(lambda m: m["type"] == "guide", 25)
        for _ in range(40):
            if top_window(OVERLAY) and find("Next ›"):
                break
            time.sleep(0.5)
        loc = VSCodeLocator(title)
        for step in tut.steps[:args.to]:
            prepare(step, win, title)
            time.sleep(1.6)                               # the locator's round, then the card settles
            g = rec.last("guide")
            if not g or g["step"]["n"] != step.n:
                rows.append({"n": step.n, "error": "no guide for this step"})
                break
            shot = grab()
            row = card_row(step, g, ov_elements(), shot.size)
            shot.save(OUT / f"step-{step.n:02d}.png")
            rows.append(row)
            print(f"  {step.n:2} {g['style']:<12} h={row.get('height')} top={row.get('top')} bottom={row.get('bottom')} on_screen={row.get('on_screen')} "
                  f"covers_target={row.get('covers_target')} covers_work={row.get('covers_work')} why={row.get('why_shown')}", flush=True)
            b = g.get("box")
            act(step, Box(**b) if b else None, win, FOLDER, title, loc, {}, OUT)
            if step.n < len(tut.steps):
                bring_front(win)
                k = rec.mark()
                hotkey("right")
                if not wait_step(rec, step.n + 1, k):
                    rows.append({"n": step.n + 1, "error": "the step didn't come up"})
                    break
    finally:
        kill(eng)
        kill(ov)
        (OUT / "cards.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    bad = [r for r in rows if r.get("error") or r.get("card") is None or not r.get("on_screen") or r.get("covers_target") or r.get("why_shown") is False]
    print(f"{len(rows)} steps, {len(bad)} with a problem; tallest card {max((r.get('height') or 0) for r in rows)} px; {OUT / 'cards.json'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
