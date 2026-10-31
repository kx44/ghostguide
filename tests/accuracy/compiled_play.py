"""Does a compiled mug play? The compiled file on the real engine, overlay and SolidWorks, all the way. Hands come from the
engine's own guidance, as in mug_walk: real clicks on the box in each `guide`. Canvas steps can't take the engine's line (a
sketch needs exact endpoints), so they use the same geometry as mug_walk, picked by the step's title: a step whose title
isn't known here stops the run.

Nothing in the compiled file is edited first. A step the engine can't find or check is written down, not fixed.

Takes the mouse and keyboard; don't touch them while it runs. Works in a new unsaved part only, and maximises SolidWorks,
because the sketch geometry is measured in that view. Spark and Wonder may be called, so this spends (cents). Model checks
are off, so no GPU starts.

    py -m tests.accuracy.compiled_play --tutorial tutorials/compiled/mug-solidworks.compiled.md
    py -m tests.accuracy.compiled_play --tutorial tutorials/compiled/mug-solidworks.compiled.md --from 22 --to 28

Results: cache/logs/compiled_play.json, screenshots in cache/screenshots/solidworks/.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time

from engine import config
from engine.appmap.store import AppMapStore
from engine.basefile.parse import parse_file
from engine.dpi import make_dpi_aware
from engine.live.locate import solidworks as sw
from tests.accuracy import mug_walk as mw
from tests.accuracy import sw_drive as d

AUTO_WAIT_S = 25.0




class Hands:
    """The canvas steps of the compiled mug, by title, with mug_walk's geometry: a tapered wall, 40 to 44 mm out."""

    def __init__(self, w: mw.Walk):
        self.w = w
        o = w.mm
        self.wall_a, self.wall_b = o(40, -50), o(44, 50)
        self.inner_a, self.inner_b = o(37, -49.88), o(41, 50.12)
        self.view = None
        self.start = (self.wall_x(30), 30)

    @staticmethod
    def wall_x(y: float) -> float:
        return 38.5 + 0.04 * (y + 49.88)      # the middle of the wall, so the handle runs into the mug

    def draw_vertical_centerline(self):
        w = self.w
        w.chain((w.origin[0], w.origin[1] - 400), (w.origin[0], w.origin[1] + 400), end=False)
        d.keys("Esc", settle=0.3)

    def sketch_outer_wall_profile(self):
        self.w.chain(self.wall_a, self.wall_b)

    def select_outer_wall_profile(self):
        d.click((self.wall_a[0] + self.wall_b[0]) // 2, (self.wall_a[1] + self.wall_b[1]) // 2, settle=0.8)

    def enter_offset_distance(self):
        rev = [e for e in d.dump() if e["type"] == "CheckBox" and e.get("name") == "Reverse"]
        if rev:                               # the file doesn't say which side; a mug's wall goes inside
            r = rev[0]["rect"]
            d.click(r[0] + 12, r[1] + r[3] // 2, settle=0.8)
        return self.w.do_it(13, presses=1)

    def draw_top_closing_line(self):
        d.keys("L", settle=0.6)
        self.w.chain(self.wall_b, self.inner_b)

    def draw_bottom_closing_line(self):
        d.keys("L", settle=0.6)               # closes the end across the axis, which is what gives the mug a base
        o = self.w.mm
        self.w.chain(self.wall_a, o(40, -52), o(0, -52), o(0, -49.88), self.inner_a)

    def select_profile_outer_edge(self):
        d.click(*self.w.mm(42, 0), settle=0.8)

    def select_axis_of_revolution(self):
        if sw.pm_ok(d.dump()):
            return {"how": "Revolve took the only centerline as its axis by itself; nothing to pick"}
        w = self.w
        d.click(w.origin[0], w.origin[1] - 350, settle=1.0)
        return {"how": "picked the centerline"}

    def draw_handle_profile(self):
        w = self.w
        self.view = w.measure()
        m = self.view
        w.chain(w.at(m, *self.start), w.at(m, 75, 30), w.at(m, 75, -20), w.at(m, self.wall_x(-20), -20))
        return {"px_mm": round(m[0], 2)}

    def round_handle_corners(self):
        w = self.w
        out = w.click_target(27)
        if w.e.current != 27:
            return out
        time.sleep(1.0)
        m = self.view or w.measure()
        for corner in ((75, 30), (75, -20)):      # the tool waits for corners, and the file has no step for them
            d.click(*w.at(m, *corner), settle=0.8)
        ok = sw.pm_ok(d.dump())
        if ok:
            r = ok["rect"]
            d.click(r[0] + r[2] // 2, r[1] + r[3] // 2, settle=1.5)
        d.keys("Esc", settle=0.4)
        return {**out, "note": "picked both corners and pressed OK, which the file doesn't ask for"}

    def select_handle_endpoint_for_plane(self):
        w = self.w
        w.view = self.view = self.view or w.measure()
        x, y = w.at(self.view, 60, self.start[1])     # on the path's top segment, then left along it to where it starts
        img, origin = d.shot("path")
        grey = img.convert("L")
        row = next((yy for yy in range(y - 12, y + 13) if grey.getpixel((x - origin[0], yy - origin[1])) < 190), y)
        while grey.getpixel((x - 1 - origin[0], row - origin[1])) < 190 and x > 600:
            x -= 1
        d.hover(x, row, settle=0.6)
        d.click(x, row, settle=1.5)
        return {"start_at": [x, row]}

    def _row(self, label: str):
        e = sw.tree_item(d.dump(), label)     # the flyout tree repeats the rows, and its one is on top
        return (e["rect"][0] + e["rect"][2] // 2, e["rect"][1] + e["rect"][3] // 2) if e else None

    def place_slot_centerpoint(self):
        w = self.w
        self.view = w.measure()
        k, o = self.view
        self.slot = (o[0], round(o[1] - 30 * k))
        w.chain(self.slot, end=False)

    def drag_slot_width(self):
        self.w.chain((self.slot[0] + round(6 * self.view[0]), self.slot[1]), end=False)

    def drag_slot_length(self):
        self.w.chain((self.slot[0], self.slot[1] - round(2.5 * self.view[0])))

    def _flyout(self, n: int, label: str, box: int):
        if self._row(label) is None:          # the flyout tree over the canvas starts folded
            for e in d.dump():
                if e["type"] == "TreeItem" and 300 < e["rect"][0] < 800 and e["rect"][1] < 300:
                    d.click(e["rect"][0] - 56, e["rect"][1] + e["rect"][3] // 2, settle=0.8)
                    break
        at = self._row(label)
        if at is None:
            raise mw.Missing(f"step {n}: no {label} row")
        lists = sorted((e for e in d.dump() if e["type"] == "List" and e["rect"][0] < 300), key=lambda e: e["rect"][1])
        if len(lists) > box:                  # the card says which box it goes in: click that box first, as a person would
            r = lists[box]["rect"]
            d.click(r[0] + r[2] // 2, r[1] + r[3] // 2, settle=0.8)
        d.click(*at, settle=1.0)
        return {"how": f"clicked the {label} row"}

    def select_sweep_profile(self):
        return self._flyout(42, "Sketch3", 0)

    def select_sweep_path(self):
        return self._flyout(43, "Sketch2", 1)

    def select_edges_to_fillet(self):
        img, origin = d.shot("rim")           # the first dark pixel down a column: the outline's left end is the mug's
        grey = img.convert("L")
        box = grey.crop((520, 215, 2470, 1480)).point(lambda v: 255 if v < 70 else 0).getbbox()
        x = box[0] + 520 + 350
        y = next(y for y in range(235, 1480) if grey.getpixel((x, y)) < 70)
        d.hover(x + origin[0], y + origin[1], settle=0.6)
        d.click(x + origin[0], y + origin[1], settle=1.5)
        return {"how": "picked the rim"}


def act(step, w: mw.Walk, hands: Hands) -> dict:
    n, t = step.n, step.target
    by_title = getattr(hands, re.sub(r"\W+", "_", step.title.casefold()).strip("_"), None)
    if by_title is not None:
        return by_title() or {"how": "by title"}
    if step.action == "shortcut":
        keys = step.params.get("keys") or [t.shortcut]
        d.keys(*[{"Escape": "Esc"}.get(str(k), str(k)) for k in keys], settle=0.8)
        return {"how": "pressed the step's keys"}
    if step.action == "menu_path":
        w.box(n)
        short = (w.g(n) or {"extra": {}})["extra"].get("shortcut")
        if short and w.e.current == n:        # the card offers it, and a person would take it over a small icon
            d.keys(*[k.strip() for k in short.split("+")], settle=2.0)
            return {"how": f"the card's shortcut, {short}"}
        out = w.follow_hops(n)
        g = w.g(n)
        if g and w.e.current == n and g["extra"].get("path_done", 0) < len(g["extra"].get("path") or [0]) - 1:
            raise mw.Missing(f"step {n}: the route didn't get to its last chip")     # the next steps would run on nothing
        return out
    if step.action == "type":
        return {"how": "Fill it for me", **w.do_it(n, presses=1)}
    if step.action in ("wait", "look"):
        w.e.send("next")
        return {"how": "next"}
    if step.action == "click":
        return w.click_target(n, count=2 if step.params.get("click_type") == "double" else 1)
    return {"how": f"no hands for {step.action}: {step.title}", "stop": True}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tutorial", required=True)
    ap.add_argument("--from", dest="start", type=int, default=1, help="carry on from this step, with SolidWorks as it is")
    ap.add_argument("--to", type=int, default=None)
    args = ap.parse_args(argv)
    print("DPI:", make_dpi_aware())
    tut = parse_file(args.tutorial)
    store = AppMapStore(tut.meta.app, version="2026", local=config.CACHE / "appmaps-check")
    mw.TUTORIAL = args.tutorial
    os.environ["CHECK_MODELS"] = "off"      # rules and pixels only: no GPU starts for this
    fresh = args.start == 1
    d.u32.ShowWindow(d.win().hwnd, 3)        # maximised: the geometry is measured in that view
    time.sleep(1.5)
    d.front()
    if fresh:
        mw.close_scratch_part()
    eng = mw.Engine(restart=fresh)
    rows = []
    try:
        w = mw.Walk(eng)
        w.must_work = set()
        hands = Hands(w)
        w.wait(lambda: eng.state is not None, 40)
        w.wait(lambda: eng.start_check is not None or eng.guide is not None, 20)
        if eng.start_check:
            eng.send("start_ok")
        if not fresh and eng.current != args.start:
            eng.ws.send(json.dumps({"type": "jump", "n": args.start}))
            w.wait(lambda: eng.current == args.start, 8)
        for step in tut.steps[args.start - 1:args.to]:
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
                row.update(act(step, w, hands))
            except mw.Missing as e:
                row["missing"] = str(e)
                row["stop"] = True      # everything after it would run on the wrong screen
            g = w.g(n)
            if g and g.get("box"):
                row["box"] = g["box"]
            d.hover(1400, 1450, settle=0.1)
            mw.overlay_shot(n)
            row["auto"] = False if row.get("stop") else w.wait(lambda: eng.current != n, AUTO_WAIT_S)
            short = step.target.shortcut or (store.get(step.target.label).shortcut if store.get(step.target.label) else None)
            if not row["auto"] and not row.get("stop") and step.action == "click" and short and step.verify:
                d.front()                # the click missed and the rule still says no: what a person does next
                d.keys(*[k.strip() for k in short.split("+")], settle=1.0)
                row["shortcut_after_miss"] = short
                row["auto"] = w.wait(lambda: eng.current != n, AUTO_WAIT_S)
            if not row["auto"] and eng.current == n and not row.get("stop"):
                eng.send("next")
                w.wait(lambda: eng.current != n, 5)
            print(f"    {json.dumps({k: v for k, v in row.items() if k not in ('n', 'action', 'label', 'title')}, ensure_ascii=False)[:260]}", flush=True)
            rows.append(row)
            if row.get("stop"):
                break
    finally:
        eng.stop()
        tree = [e.get("name") for e in d.dump() if e["type"] == "TreeItem" and re.match(r"(\(-\) )?(Sketch|Revolve|MugEdge|Plane|Sweep|Fillet)\d?$", e.get("name") or "")]
        print("in the tree:", tree, flush=True)
        (mw.LOGS / "compiled_play.json").write_text(json.dumps({"tree": tree, "steps": rows}, indent=1, ensure_ascii=False), encoding="utf-8")
    acted = [r for r in rows if not r.get("already")]
    summary = {"steps": len(rows), "found_or_keyed": sum(1 for r in acted if not r.get("missing")), "moved_on_by_itself": sum(1 for r in rows if r.get("auto") or r.get("already")),
               "missing": [r["n"] for r in rows if r.get("missing")], "needed_next": [r["n"] for r in acted if not r.get("auto")]}
    print(json.dumps(summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
