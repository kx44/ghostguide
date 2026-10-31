"""Does a compiled mug play? The compiled file on the real engine, overlay and SolidWorks, for its first stretch: the body,
up to the revolve. Hands come from the engine's own guidance, as in mug_walk: real clicks on the box in each `guide`, and
the step's words only say which of a few sketch lines to draw, because a sketch needs exact endpoints.

Nothing in the compiled file is edited first. A step the engine can't find or check is written down, not fixed.

Takes the mouse and keyboard; don't touch them while it runs. Works in a new unsaved part only. Spark may be called for
ribbon icons, so this can spend (cents). Model checks are off, so no GPU starts.

    py -m tests.accuracy.compiled_play --tutorial tutorials/compiled/mug-solidworks.compiled.md --to 20

Results: cache/logs/compiled_play.json, screenshots in cache/screenshots/solidworks/.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time

from engine.basefile.parse import parse_file
from engine.dpi import make_dpi_aware
from tests.accuracy import mug_walk as mw
from tests.accuracy import sw_drive as d

AUTO_WAIT_S = 25.0


def sketch_line(step, w: mw.Walk) -> list[tuple[int, int]] | None:
    """Which line of the body's sketch a draw step means, from its words. None = not one this harness can draw."""
    words = " ".join([step.title, step.target.label, step.target.where or "", str(step.params)]).casefold()
    o = w.mm
    wall_a, wall_b = o(40, -50), o(44, 50)
    ia, ib = o(38, -49.92), o(42, 50.08)
    if "centerline" in words or "centre line" in words or "axis" in words:
        return [(w.origin[0], w.origin[1] - 400), (w.origin[0], w.origin[1] + 400)]
    if "top" in words:
        return [wall_b, ib]
    if "bottom" in words or "base" in words:
        return [wall_a, ia]
    if "close" in words or "cap" in words or "end" in words:
        return [wall_b, ib]
    if "wall" in words or "profile" in words or "outer" in words or "edge" in words:
        return [wall_a, wall_b]
    return None


def act(step, w: mw.Walk) -> dict:
    n, t = step.n, step.target
    if step.action == "shortcut":
        keys = step.params.get("keys") or [t.shortcut]
        d.keys(*[{"Escape": "Esc"}.get(str(k), str(k)) for k in keys], settle=0.8)
        return {"how": "pressed the step's keys"}
    if step.action == "menu_path":
        return w.follow_hops(n)
    if step.action == "draw_line":
        pts = sketch_line(step, w)
        if not pts:
            return {"how": "no hands for this line", "stop": True}
        w.chain(*pts, end=False)
        d.keys("Esc", settle=0.3)
        d.keys("Esc", settle=0.5)
        return {"how": f"drew it, {len(pts)} points"}
    if step.action == "pick":
        wall = w.mm(42, 0)
        d.click(*wall, settle=0.8)
        return {"how": "picked the wall line"}
    if step.action == "type":
        out = w.do_it(n, presses=1)
        return {"how": "Fill it for me", **out}
    if step.action in ("wait", "look"):
        w.e.send("next")
        return {"how": "next"}
    if step.action == "click":
        count = 2 if step.params.get("click_type") == "double" else 1
        return w.click_target(n, count=count)
    return {"how": f"no hands for {step.action}", "stop": True}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tutorial", required=True)
    ap.add_argument("--to", type=int, default=20)
    args = ap.parse_args(argv)
    print("DPI:", make_dpi_aware())
    tut = parse_file(args.tutorial)
    mw.TUTORIAL = args.tutorial
    os.environ["CHECK_MODELS"] = "off"      # rules and pixels only: no GPU starts for this
    d.front()
    mw.close_scratch_part()
    eng = mw.Engine(restart=True)
    rows = []
    try:
        w = mw.Walk(eng)
        w.must_work = set()
        w.wait(lambda: eng.state is not None, 40)
        w.wait(lambda: eng.start_check is not None or eng.guide is not None, 20)
        if eng.start_check:
            eng.send("start_ok")
        for step in tut.steps[:args.to]:
            n = step.n
            w.wait(lambda: eng.current >= n and (eng.current > n or w.g(n) is not None), 30)
            row = {"n": n, "action": step.action, "label": step.target.label, "title": step.title, "has_verify": bool(step.verify)}
            print(f"--- {n}: {step.title} [{step.action} {step.target.label!r}]", flush=True)
            if eng.current > n:
                row["already"] = True
                rows.append(row)
                continue
            d.front()
            time.sleep(0.2)
            g = w.g(n)
            row["style"] = g["style"] if g else None
            try:
                row.update(act(step, w))
            except mw.Missing as e:
                row["missing"] = str(e)
            g = w.g(n)
            if g and g.get("box"):
                row["box"] = g["box"]
            d.hover(1400, 1450, settle=0.1)
            mw.overlay_shot(n)
            row["auto"] = w.wait(lambda: eng.current != n, AUTO_WAIT_S)
            if not row["auto"] and eng.current == n:
                eng.send("next")
                w.wait(lambda: eng.current != n, 5)
            print(f"    {json.dumps({k: v for k, v in row.items() if k not in ('n', 'action', 'label', 'title')}, ensure_ascii=False)[:260]}", flush=True)
            rows.append(row)
            if row.get("stop"):
                break
    finally:
        eng.stop()
        tree = [e.get("name") for e in d.dump() if e["type"] == "TreeItem" and re.match(r"(\(-\) )?(Sketch|Revolve)\d", e.get("name") or "")]
        print("in the tree:", tree, flush=True)
        (mw.LOGS / "compiled_play.json").write_text(json.dumps({"tree": tree, "steps": rows}, indent=1, ensure_ascii=False), encoding="utf-8")
    acted = [r for r in rows if not r.get("already")]
    summary = {"steps": len(rows), "found_or_keyed": sum(1 for r in acted if not r.get("missing")), "moved_on_by_itself": sum(1 for r in rows if r.get("auto") or r.get("already")),
               "missing": [r["n"] for r in rows if r.get("missing")], "needed_next": [r["n"] for r in acted if not r.get("auto")]}
    print(json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
