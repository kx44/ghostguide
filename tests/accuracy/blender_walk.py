"""The compiled barrel tutorial on real Blender, with hands: the first run on Blender, to see what the product does there.

Acts only where the engine points, as mug_walk does, so a box in the wrong place shows up as a later step failing. Nothing in
the compiled file is edited. A step the engine can't find or check is written down and the run carries on with Next. Models are
on, so this spends, and Glimmer starts a GPU. Takes the mouse and keyboard; don't touch them while it runs. Blender starts from
factory settings, so nothing of yours changes, and nothing is saved.

    py -m tests.accuracy.blender_walk
    py -m tests.accuracy.blender_walk --to 10

Results: cache/logs/blender_walk.json, cache/logs/mug_walk-engine.log, cache/screenshots/blender/stepNN.png.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import subprocess
import time

from engine import config
from engine.basefile.parse import parse_file
from engine.dpi import make_dpi_aware
from engine.live import windows
from tests.accuracy import mug_walk as mw
from tests.accuracy import sw_drive as d

TUTORIAL = "tutorials/compiled/blender-barrel.compiled.md"
BLENDER = r"C:\Program Files\Blender Foundation\Blender 5.2\blender-launcher.exe"
BOX_WAIT_S = 45.0
AUTO_WAIT_S = 15.0
VK = {"shift": 0x10, "ctrl": 0x11, "alt": 0x12}
u32 = ctypes.windll.user32
KEEP_MOUSE = {15, 16, 17, 38}     # a Blender popover closes when the mouse leaves it
TOP_CUT, BOTTOM_CUT = (1058, 702), (1058, 826)
TOP_RING, BOTTOM_RING = (1058, 695), (1058, 834)
THICKNESS = (2406, 580)           # the first number in a Solidify panel, measured


def show_off() -> None:
    """The finished thing, framed and turning, as anyone looks at what they've just made."""
    d.hover(*viewport(), settle=0.3)
    d.keys("A", settle=0.5)
    u32.keybd_event(0x6E, 0, 0, 0)     # numpad full stop: frame what's selected
    u32.keybd_event(0x6E, 0, 2, 0)
    time.sleep(1.5)
    d.keys("Alt", "A", settle=1.0)
    for _ in range(26):
        u32.keybd_event(0x66, 0, 0, 0)  # numpad 6: orbit
        u32.keybd_event(0x66, 0, 2, 0)
        time.sleep(0.35)
    time.sleep(1.0)


def viewport() -> tuple[int, int]:
    """The middle of the object, in the default view of a maximised window at this screen size: where the cube was found."""
    return 1090, 720


def press(*names: str) -> None:
    """Keys over the object: Blender sends a key to the area under the mouse, and a loop cut needs the mesh under it."""
    d.hover(*viewport(), settle=0.2)
    if names == ("Wheel Up",):
        u32.mouse_event(0x0800, 0, 0, 120, 0)
        time.sleep(0.5)
    else:
        d.keys(*names, settle=0.8)


def click_with(keys: tuple[str, ...], x: int, y: int) -> None:
    d.hover(x, y, settle=0.3)
    for k in keys:
        u32.keybd_event(VK[k], 0, 0, 0)
        time.sleep(0.15)
    try:
        d.click(x, y, settle=0.8)
    finally:
        for k in reversed(keys):
            u32.keybd_event(VK[k], 0, 2, 0)


OUTLINER_TOP, OUTLINER_ROW, NAME_X, EYE_X = 184, 29, 2260, 2498
OUTLINER = {29: (1, NAME_X), 31: (2, NAME_X), 33: (2, EYE_X), 35: (0, NAME_X), 49: (1, NAME_X), 52: (4, NAME_X), 54: (2, EYE_X), 55: (2, NAME_X)}    # row by name order
RENAMES = (30, 32, 50)


def act(step, w: mw.Walk) -> dict:
    n, kind = step.n, step.params.get("click_type")
    if n == 42:                     # the rings' cuts: one near each end of the barrel, on its front edge, measured in this view
        d.hover(*TOP_CUT, settle=0.4)
        d.keys("Ctrl", "R", settle=0.8)
        return {"how": "started the top cut"}
    if n == 43:
        d.click(*TOP_CUT, settle=0.5)
        d.click(*TOP_CUT, settle=0.8)
        d.hover(*BOTTOM_CUT, settle=0.4)
        d.keys("Ctrl", "R", settle=0.8)
        d.click(*BOTTOM_CUT, settle=0.5)
        d.click(*BOTTOM_CUT, settle=0.8)
        return {"how": "placed both cuts"}
    if n == 45:                     # Alt on a side edge takes the ring of faces round the barrel
        click_with(("alt",), *TOP_RING)
        return {"how": "Alt-clicked the top ring"}
    if n == 46:
        click_with(("shift", "alt"), *BOTTOM_RING)
        return {"how": "Shift+Alt-clicked the bottom ring"}
    if step.action == "shortcut":
        keys = [str(k) for k in step.params.get("keys") or []]
        press(*keys)
        if step.n == 10:            # the card says three cuts: two notches from one
            press(*keys)
        return {"how": f"pressed {keys}"}
    if n in RENAMES:                # the row was double-clicked in the step before, so its name is open
        d.keys("Ctrl", "A", settle=0.2)
        d.text(str(step.params["value"]))
        d.keys("Enter", settle=0.8)
        return {"how": f"typed {step.params['value']}"}
    t0 = time.monotonic()
    b = w.box(n, 20.0 if n in OUTLINER else BOX_WAIT_S)
    if n in OUTLINER and b is None:
        row, x = OUTLINER[n]
        d.click(x, OUTLINER_TOP + row * OUTLINER_ROW, count=2 if kind == "double" else 1, settle=0.8)
        return {"found_s": round(time.monotonic() - t0, 1), "box": None, "how": "clicked the row, measured: nothing pointed at it"}
    out: dict = {"found_s": round(time.monotonic() - t0, 1), "box": b}
    g = w.g(n)
    if g:
        out.update(style=g.get("style"), route=bool(g["extra"].get("route")), do_it="do_it" in (g.get("card") or {}).get("actions", []),
                   shortcut=g["extra"].get("shortcut") or (g["extra"].get("route") or {}).get("shortcut"))
    if w.e.current != n:
        return {**out, "how": "moved on while it looked"}
    if step.action == "menu_path" or (b is None and g and g["extra"].get("route") and step.action == "click"):
        for attempt in range(3):
            try:
                got = w.follow_hops(n)
                if w.e.current != n or (w.g(n) and w.g(n)["extra"].get("path_done", 0) >= len(w.g(n)["extra"].get("path") or [0]) - 1):
                    return {**out, **got, "how": "route", "tries": attempt + 1}
            except mw.Missing as e:
                out["missing"] = str(e)
            press("Esc")
            press("Esc")
            time.sleep(1.5)
        return {**out, "missing": "the route didn't get to its last chip"}
    if step.action == "type":
        value = str(step.params.get("value", ""))
        if step.target.label == "Search":           # an open Blender menu takes typing as a search
            d.text(value)
            time.sleep(0.8)
            return {**out, "how": f"typed {value} into the open menu"}
        if step.target.kind != "canvas":
            if out.get("do_it"):
                return {**out, **w.do_it(n), "how": "Do it for me"}
            if b is None and step.target.label != "Thickness":
                return {**out, "missing": "no box to type into"}
            d.click(*(mw.box_center(b) if b else THICKNESS), count=2, settle=0.6)
            d.keys("Ctrl", "A", settle=0.2)
        d.text(value)
        d.keys(str(step.params.get("then_key", "Enter")), settle=0.8)
        return {**out, "how": f"typed {value}"}
    if step.target.label == "Barrel":               # a loop cut: one click places it, one ends the slide
        d.click(*viewport(), settle=0.5)
        d.click(*viewport(), settle=0.8)
        return {**out, "how": "placed the cut in the middle of the object"}
    if b is None:
        short = out.get("shortcut")
        if short and "," not in short and " or " not in short:
            press(*[k.strip() for k in short.replace("-", "+").split("+")])
            return {**out, "how": f"the card's shortcut, {short}"}
        return {**out, "missing": "no box and no shortcut"}
    at = mw.box_center(b)
    if kind in VK:
        click_with((kind,), *at)
    else:
        d.click(*at, count=2 if kind == "double" else 1, settle=0.8)
    return {**out, "how": f"clicked ({kind or 'single'})"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="start", type=int, default=1, help="carry on from this step, with Blender as it is")
    ap.add_argument("--to", type=int, default=None)
    args = ap.parse_args(argv)
    print("DPI:", make_dpi_aware())
    d.WINDOW = "Blender"
    d.SHOTS = config.CACHE / "screenshots" / "blender"
    mw.RIBBON_BOTTOM = -1           # Blender draws its own tooltips, so resting the mouse tells the engine nothing
    tut = parse_file(TUTORIAL)
    fresh = args.start == 1
    if fresh:
        subprocess.Popen([BLENDER, "--factory-startup", "--python-expr", "import bpy; bpy.context.preferences.view.show_splash = False"])
    for _ in range(120):            # it can start minimised, and a minimised window can't be found by name
        time.sleep(0.5)
        own = [w for w in windows.top_windows() if windows.program(w.hwnd).exe == "blender" and w.title]
        if own:
            u32.ShowWindow(own[0].hwnd, 3)
            break
    else:
        raise SystemExit("Blender didn't open")
    time.sleep(4 if fresh else 1)
    d.front()
    mw.TUTORIAL = TUTORIAL
    eng = mw.Engine(restart=fresh)
    rows = []
    out_file = config.LOGS / f"blender_walk-{args.start}.json"
    try:
        w = mw.Walk(eng)
        w.wait(lambda: eng.state is not None, 40)
        w.wait(lambda: eng.start_check is not None or eng.guide is not None, 20)
        if eng.start_check:
            eng.send("start_ok")
        if not fresh and eng.current != args.start:
            eng.ws.send(json.dumps({"type": "jump", "n": args.start}))
            w.wait(lambda: eng.current == args.start, 8)
        started = time.monotonic()
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
            try:
                row.update(act(step, w))
            except d.Stop as e:
                row["stopped"] = str(e)
                print("    STOPPED:", e, flush=True)
                rows.append(row)
                break
            time.sleep(0.5)
            if not (step.action in ("click", "shortcut") and step.title.startswith("Open ")) and step.n not in KEEP_MOUSE:
                d.hover(*viewport(), settle=0.1)
            mw.overlay_shot(n)
            row["toast"] = eng.toasts[-1] if eng.toasts else None
            row["auto"] = w.wait(lambda: eng.current != n, AUTO_WAIT_S)
            if not row["auto"] and eng.current == n:
                eng.send("next")
                w.wait(lambda: eng.current != n, 5)
            print("   ", json.dumps({k: v for k, v in row.items() if k not in ("n", "action", "label", "title")}, ensure_ascii=False)[:300], flush=True)
            rows.append(row)
            if row.get("missing") and step.action == "menu_path":
                print("    STOPPED: a menu route failed, and the next steps would run on nothing", flush=True)
                break
            out_file.write_text(json.dumps({"seconds": round(time.monotonic() - started), "steps": rows}, indent=1, ensure_ascii=False), encoding="utf-8")
        if args.to is None and rows and rows[-1]["n"] == len(tut.steps):
            show_off()
    finally:
        try:
            mw.overlay_shot(100 + (args.to or 57))
        finally:
            eng.stop()
    acted = [r for r in rows if not r.get("already")]
    print(json.dumps({"steps": len(rows), "found": sum(1 for r in acted if r.get("box")), "missing": [r["n"] for r in rows if r.get("missing")],
                      "moved_on_by_itself": sum(1 for r in rows if r.get("auto") or r.get("already")), "needed_next": [r["n"] for r in acted if not r.get("auto")]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
