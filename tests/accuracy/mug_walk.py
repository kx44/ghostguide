"""The mug tutorial, live, end to end (phase 4 "done when"): the real engine and overlay over real SolidWorks, with hands.

Listens on the engine's WebSocket like the overlay does and acts only where the engine points: real clicks on the box
in each `guide`, so a box in the wrong place shows up as the next step failing. Canvas drawing can't take the engine's
line (a sketch needs exact endpoints), so it uses its own geometry, measured from the view, and logs how far Spark's
line was. Then it waits for the step to move on by itself; if it doesn't, it presses Next and counts that against the
run. Works in a new unsaved part only: it refuses to close anything that has been saved.

Takes the mouse and keyboard; don't touch them while it runs.

    py -m tests.accuracy.mug_walk                 # all steps, from a fresh start
    py -m tests.accuracy.mug_walk --to 20         # stop after step 20 and leave it there
    py -m tests.accuracy.mug_walk --from 21       # carry on from the saved progress

Results: cache/logs/mug_walk.json, cache/logs/mug_walk-engine.log, cache/screenshots/solidworks/stepNN.png.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from engine import config
from engine.dpi import make_dpi_aware
from engine.live.locate import solidworks as sw
from tests.accuracy import sw_drive as d

TUTORIAL = "tutorials/mug-solidworks.md"
LOGS = config.LOGS
PORT = 8765
AUTO_WAIT_S = 40.0         # for a step to move on by itself
BOX_WAIT_S = 70.0          # for a target to be found (a first Spark call, a cold Glimmer)


class Missing(SystemExit):
    """Nothing to act on: stop here, so the next steps don't click blind."""


class Engine:
    """The engine and overlay as processes, and what the engine last said."""

    def __init__(self, restart: bool):
        cmd = [sys.executable, "-u", "-m", "engine", "play", TUTORIAL] + (["--restart"] if restart else [])
        env = {**os.environ, "GG_LOCAL_APPMAPS": str(config.CACHE / "appmaps-check"), "PYTHONIOENCODING": "utf-8"}
        LOGS.mkdir(parents=True, exist_ok=True)
        self.proc = subprocess.Popen(cmd, cwd=config.ROOT, env=env, stdout=(LOGS / "mug_walk-engine.log").open("w", encoding="utf-8"),
                                     stderr=subprocess.STDOUT)
        self.state: Optional[dict] = None
        self.guide: Optional[dict] = None
        self.start_check: Optional[dict] = None
        self.toasts: list[str] = []
        self.ws = None
        self._connect()
        threading.Thread(target=self._read, daemon=True).start()
        self.overlay = subprocess.Popen("npm start", shell=True, cwd=config.ROOT / "overlay",
                                        stdout=(LOGS / "mug_walk-overlay.log").open("w"), stderr=subprocess.STDOUT)

    def _connect(self) -> None:
        from websockets.sync.client import connect
        for _ in range(60):
            try:
                self.ws = connect(f"ws://127.0.0.1:{PORT}", max_size=2 ** 22, ping_interval=None)
                return
            except OSError:
                time.sleep(0.5)
        raise SystemExit("the engine didn't start; see cache/logs/mug_walk-engine.log")

    def _read(self) -> None:
        self.lost = None
        try:
            for raw in self.ws:
                m = json.loads(raw)
                t = m["type"]
                if t == "state":
                    self.state = m
                elif t == "guide":
                    self.guide, self.start_check = m, None
                elif t == "clear":
                    self.guide = None
                elif t == "start_check":
                    self.start_check = m
                elif t == "toast":
                    self.toasts.append(m["text"])
        except Exception as e:
            self.lost = repr(e)
            print("LOST THE ENGINE:", self.lost, flush=True)

    def send(self, kind: str) -> None:
        self.ws.send(json.dumps({"type": kind}))

    @property
    def current(self) -> int:
        return self.state["current"] if self.state else 0

    def stop(self) -> None:
        for p in (self.overlay, self.proc):
            subprocess.run(f"taskkill /PID {p.pid} /T /F", shell=True, capture_output=True)


def box_center(b: dict) -> tuple[int, int]:
    return b["x"] + b["w"] // 2, b["y"] + b["h"] // 2


def overlay_shot(n: int) -> None:
    from PIL import ImageGrab
    d.SHOTS.mkdir(parents=True, exist_ok=True)
    ImageGrab.grab(all_screens=True).save(d.SHOTS / f"step{n:02d}.png")


def close_scratch_part() -> None:
    """Only a part that has never been saved ("Part3", "Part3 *"): nothing of yours is ever closed."""
    cancel = next((e for e in d.dump() if e["type"] == "Window" and e.get("name") == sw.NEW_DIALOG), None)
    if cancel is not None:                  # a New dialog left open by an aborted run
        d.front()
        d.keys("Esc", settle=1.0)
    for _ in range(4):
        title = d.win().title
        m = re.search(r"\[(.+?)\]\s*$", title)
        if not m:
            return
        if not re.fullmatch(r"(Sketch\d+ of )?Part\d+( \*)?", m.group(1)):
            raise SystemExit(f"'{m.group(1)}' is open: close it yourself; this only closes new unsaved parts")
        d.front()
        d.keys("Esc", settle=0.3)
        d.keys("Esc", settle=0.3)
        d.keys("Ctrl", "W", settle=1.5)
        for e in d.dump():
            if e["type"] == "Button" and e.get("name") and "don't save" in e["name"].casefold().replace("’", "'"):
                d.click(*box_center(dict(zip("xywh", e["rect"]))), settle=1.5)
                break


class Walk:
    def __init__(self, eng: Engine):
        self.e = eng
        self.rows: list[dict] = []
        self.must_work = {2, 5, 8, 11, 13, 16, 18, 20, 27, 29, 30, 31, 34, 37, 38, 39, 40, 41, 43, 44, 45}
        self.view = None
        self.origin = (1413, 833)     # the front view puts it in the middle of the graphics area
        self.px_mm = 5.81             # in a new part's front view (a 400 px line read 68.83 mm)

    # ---------- waiting for the engine ----------
    def wait(self, ok: Callable[[], bool], s: float) -> bool:
        t0 = time.monotonic()
        while time.monotonic() - t0 < s:
            if ok():
                return True
            time.sleep(0.1)
        return ok()

    def g(self, n: int) -> Optional[dict]:
        g = self.e.guide
        return g if g and g["step"]["n"] == n else None

    def box(self, n: int, s: float = BOX_WAIT_S) -> Optional[dict]:
        self.wait(lambda: self.e.current != n or bool(self.g(n) and self.g(n).get("box")), s)
        g = self.g(n)
        return g.get("box") if g else None

    # ---------- doing ----------
    def click_target(self, n: int, count: int = 1, button: str = "left") -> dict:
        """Click where the engine points, following its route if the control is behind one: a ribbon tab to open."""
        for _ in range(4):
            b = self.box(n)
            if b is None or self.e.current != n:
                break
            g = self.g(n)
            routed = bool(g and g["extra"].get("route"))
            d.click(*box_center(b), count=1 if routed else count, button=button, settle=0.8)
            if not routed:
                return {"clicked": b}
            self.wait(lambda: self.g(n) is None or not self.g(n)["extra"].get("route"), 14)
            time.sleep(1.5)
        g = self.g(n)
        short = g and ((g["extra"].get("route") or {}).get("shortcut") or g["extra"].get("shortcut"))
        if short and self.e.current == n:      # the card offers it too: what a person would do
            d.keys(*[k.strip() for k in short.split("+")], settle=0.8)
            return {"clicked": None, "shortcut": short}
        raise Missing(f"step {n}: the engine pointed at nothing")

    def follow_hops(self, n: int) -> dict:
        """A menu_path step: click each chip's control as the engine moves along the route."""
        hops = []
        for _ in range(5):
            b = self.box(n)
            if b is None or self.e.current != n:
                break
            extra = self.g(n)["extra"]
            done = extra.get("path_done", 0)
            hops.append(b)
            d.click(*(extra.get("click_at") or box_center(b)), settle=0.8)
            if done >= len(extra.get("path") or [0]) - 1:     # that was the last chip
                return {"hops": hops}
            self.wait(lambda: self.e.current != n or (self.g(n) and self.g(n)["extra"].get("path_done", 0) != done), 40)
            if self.e.current != n or self.g(n) is None or self.g(n)["extra"].get("path_done", 0) == done:
                break
            time.sleep(0.8)
        if not hops:
            short = self.e.state and self.g(n) and self.g(n)["extra"].get("shortcut")
            if not short:
                raise Missing(f"step {n}: no box and no shortcut")
            d.keys(*[k.strip() for k in short.split("+")], settle=0.8)
            return {"hops": [], "shortcut": short}
        return {"hops": hops}

    def do_it(self, n: int, presses: int = 2) -> dict:
        self.wait(lambda: self.e.current != n or bool(self.g(n) and "do_it" in (self.g(n).get("card") or {}).get("actions", [])), BOX_WAIT_S)
        said = len(self.e.toasts)
        for _ in range(presses):
            self.e.send("do_it")
            self.wait(lambda: len(self.e.toasts) > said, 6)
            said = len(self.e.toasts)
            if self.e.toasts and "Check the outline" not in self.e.toasts[-1]:
                break
        if self.e.current == n and self.e.toasts and "nothing sure" in self.e.toasts[-1]:
            return self.click_target(n)
        return {"do_it": self.e.toasts[-1] if self.e.toasts else None, "presses": presses}

    def chain(self, *pts, end: bool = True) -> None:
        for p in pts:
            d.hover(*p, settle=0.3)
            d.click(*p, settle=0.3)
        if end:
            d.keys("Esc", settle=0.3)
            d.keys("Esc", settle=0.5)

    def mm(self, x: float, y: float) -> tuple[int, int]:
        return round(self.origin[0] + x * self.px_mm), round(self.origin[1] - y * self.px_mm)

    # ---------- one step ----------
    def step(self, n: int, act: Callable[[], Optional[dict]]) -> None:
        if getattr(self.e, "lost", None):
            raise SystemExit("lost the engine; stopped so nothing is clicked blind")
        self.wait(lambda: self.e.current >= n and (self.e.current > n or self.g(n) is not None), 30)
        row = {"n": n, "title": self.e.state["titles"][n - 1] if self.e.state else "?"}
        print(f"--- {n}: {row['title']}", flush=True)
        if self.e.current > n:
            row["already"] = True          # a check moved it on before its turn came
        else:
            d.front()
            time.sleep(0.2)
            g = self.g(n)
            row["style"] = g["style"] if g else None
            if g and g.get("line"):
                row["line"] = g["line"]
            row.update(act() or {})
            g = self.g(n)
            if g:
                row["card"] = (g.get("card") or {}).get("actions")
                row["suggested"] = (g.get("card") or {}).get("suggested")
            d.hover(1400, 1450, settle=0.1)     # off the model, so the picture settles
            time.sleep(0.2)
            overlay_shot(n)
            d.shot(f"step{n:02d}-app")
            row["auto"] = self.wait(lambda: self.e.current != n, AUTO_WAIT_S)
            if not row["auto"] and self.e.current == n:
                if self.must_work and n in self.must_work:
                    self.rows.append(row)
                    self.save()
                    raise Missing(f"step {n} has a rule and it isn't true, so the steps after it would go wrong; stopped here")
                print(f"    NOT auto: pressing Next", flush=True)
                self.e.send("next")
                self.wait(lambda: self.e.current != n, 5)
        print(f"    {json.dumps({k: v for k, v in row.items() if k not in ('n', 'title')}, ensure_ascii=False)[:300]}", flush=True)
        self.rows.append(row)
        self.save()

    def save(self) -> None:
        (LOGS / "mug_walk.json").write_text(json.dumps(self.rows, indent=1, ensure_ascii=False), encoding="utf-8")

    # ---------- the tutorial ----------
    def plan(self) -> dict[int, Callable[[], Optional[dict]]]:
        o = self.mm
        wall_a, wall_b = o(40, -50), o(44, 50)              # the wall line: suggested length 100, radius 40, a slight taper

        def s5():  return self.follow_hops(5)
        def s6():
            self.chain((self.origin[0], self.origin[1] - 400), (self.origin[0], self.origin[1] + 400), end=False)
        def s7():
            d.keys("Esc", settle=0.3)
            d.keys("Esc", settle=0.5)
        def s9():
            self.chain(wall_a, wall_b)
        def s10():
            d.click((wall_a[0] + wall_b[0]) // 2, (wall_a[1] + wall_b[1]) // 2, settle=0.8)
        def s12():
            rev = [e for e in d.dump() if e["type"] == "CheckBox" and e.get("name") == "Reverse"]
            if rev:
                r = rev[0]["rect"]
                d.click(r[0] + 12, r[1] + r[3] // 2, settle=0.8)     # the card's note: inside, Reverse if it's outside
            return self.do_it(12, presses=1)
        ia, ib = o(38, -49.92), o(42, 50.08)                # the offset's ends: 2 mm in
        def s14():
            d.keys("L", settle=0.6)
            self.chain(wall_b, ib)
        def s15():
            d.keys("L", settle=0.6)
            self.chain(wall_a, o(40, -52), o(0, -52), o(0, -49.92), ia)

        return {
            1: lambda: self.click_target(1),
            2: lambda: self.click_target(2, count=2),
            3: lambda: self.do_it(3, presses=1),
            4: lambda: self.follow_hops(4),
            5: s5, 6: s6, 7: s7,
            8: lambda: self.do_it(8),
            9: s9, 10: s10,
            11: lambda: self.do_it(11, presses=2),         # found by sight: the first press asks you to check
            12: s12,
            13: lambda: self.click_target(13),
            14: s14, 15: s15,
            16: lambda: self.click_target(16),
            17: lambda: self.click_target(17),
            18: lambda: self.click_target(18),
            19: lambda: {"note": "360 is the default; nothing to type"},
            20: lambda: self.click_target(20),
            **self.plan_handle(),
        }

    def measure(self) -> tuple[float, tuple[int, int]]:
        """(px per mm, screen spot of the model's (0, 0)) in a straight-on view, from the mug's outline: it stands
        102 mm tall (-52 to +50), centred on the axis."""
        img, origin = d.shot("measure")
        grey = img.convert("L").crop((520, 215, 2470, 1480))    # past the corner triad, short of the task pane tabs
        box = grey.point(lambda v: 255 if v < 70 else 0).getbbox()
        if box is None:
            raise Missing("can't see the mug's outline")
        l, top, r, bottom = box[0] + 520, box[1] + 215, box[2] + 520, box[3] + 215
        k = (bottom - top) / 102.08
        return k, (round((l + r) / 2) + origin[0], round(bottom - 52 * k) + origin[1])

    def at(self, k_o, x: float, y: float) -> tuple[int, int]:
        k, o = k_o
        return round(o[0] + x * k), round(o[1] - y * k)

    def plan_handle(self) -> dict[int, Callable[[], Optional[dict]]]:
        def wall_x(y: float) -> float:          # the middle of the wall (39 mm at the base, 43 at the rim), so the
            return 39 + 0.04 * (y + 49.92)      # handle runs into the mug and the sweep merges with it
        start = (wall_x(30), 30)

        def s25():
            m = self.measure()
            self.view = m
            self.chain(self.at(m, *start), self.at(m, 75, 30), self.at(m, 75, -20), self.at(m, wall_x(-20), -20))
            return {"px_mm": round(m[0], 2)}
        def s30():
            self.view = self.view or self.measure()
            x, y = self.at(self.view, 60, start[1])    # on the path's top segment, then left along it to where it starts:
            img, origin = d.shot("path")               # it snapped to the nearest wall edge, wherever that was
            grey = img.convert("L")
            ys = max((abs(yy - y), yy) for yy in [y])[1]
            row = next((yy for yy in range(y - 12, y + 13) if grey.getpixel((x - origin[0], yy - origin[1])) < 190), ys)
            while grey.getpixel((x - 1 - origin[0], row - origin[1])) < 190 and x > 600:
                x -= 1
            d.hover(x, row, settle=0.6)
            d.click(x, row, settle=1.5)
            return {"start_at": [x, row]}
        def row(label: str) -> Optional[tuple[int, int]]:
            for e in d.dump():
                if e["type"] == "TreeItem" and sw.row_name(e.get("name")) == sw.row_name(label) and e["rect"][2] > 0:
                    return e["rect"][0] + e["rect"][2] // 2, e["rect"][1] + e["rect"][3] // 2
            return None
        def s33():
            d.keys("Esc", settle=0.3)
            part = next((e for e in d.dump() if e["type"] == "TreeItem" and re.fullmatch(r"Part\d+", e.get("name") or "")), None)
            if part:                            # away and back: a click on the selected row would start a rename
                d.click(part["rect"][0] + 10, part["rect"][1] + 12, settle=0.6)
            d.click(*row("MugEdge"), settle=0.8)
            d.keys("Ctrl", "8", settle=2.0)
        def s35():
            m = self.measure()
            self.view = m
            k, o = m
            self.slot = (o[0], round(o[1] - 30 * k))
            self.chain(self.slot, (self.slot[0] + round(6 * k), self.slot[1]), end=False)
        def s36():
            k = self.view[0]
            self.chain((self.slot[0], self.slot[1] - round(2.5 * k)))
        def flyout(n: int, label: str) -> dict:
            if row(label) is None:              # the flyout tree over the canvas starts folded
                for e in d.dump():
                    if e["type"] == "TreeItem" and 300 < e["rect"][0] < 800 and e["rect"][1] < 300:
                        d.click(e["rect"][0] - 56, e["rect"][1] + e["rect"][3] // 2, settle=0.8)
                        break
            return self.click_target(n)
        def s44():
            img, origin = d.shot("rim")         # the first dark pixel down a column: the outline's left end is the mug's
            grey = img.convert("L")
            box = grey.crop((520, 215, 2470, 1480)).point(lambda v: 255 if v < 70 else 0).getbbox()
            x = box[0] + 520 + 350
            y = next(y for y in range(235, 1480) if grey.getpixel((x, y)) < 70)
            d.hover(x + origin[0], y + origin[1], settle=0.6)
            d.click(x + origin[0], y + origin[1], settle=1.5)
        def s45():
            out = self.do_it(45, presses=2)
            ok = sw.pm_ok(d.dump())
            if ok:
                r = ok["rect"]
                d.click(r[0] + r[2] // 2, r[1] + r[3] // 2, settle=3.0)
            return out

        return {
            21: lambda: self.click_target(21),
            22: lambda: self.do_it(22, presses=1),
            23: lambda: self.follow_hops(23),
            24: lambda: self.do_it(24, presses=1),
            25: s25,
            26: lambda: {"skipped": self.e.send("skip")},
            27: lambda: self.click_target(27),
            28: lambda: self.click_target(28),
            29: lambda: self.follow_hops(29),
            30: s30,
            31: lambda: self.click_target(31),
            32: lambda: self.do_it(32, presses=1),
            33: s33,
            34: lambda: self.follow_hops(34),
            35: s35, 36: s36,
            37: lambda: self.click_target(37),
            38: lambda: self.click_target(38),
            39: lambda: flyout(39, "Sketch3"),
            40: lambda: flyout(40, "Sketch2"),
            41: lambda: self.click_target(41),
            42: lambda: {"next": self.e.send("next")},     # a look step: you say when
            43: lambda: self.click_target(43),
            44: s44, 45: s45,
        }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="start", type=int, default=1)
    ap.add_argument("--to", type=int, default=45)
    ap.add_argument("--as-is", action="store_true", help="--from: carry on with SolidWorks exactly as it is (a panel left open)")
    args = ap.parse_args(argv)
    print("DPI:", make_dpi_aware())
    fresh = args.start == 1
    d.front()
    eng = Engine(restart=fresh)
    try:
        w = Walk(eng)
        w.wait(lambda: eng.state is not None, 40)
        if fresh:
            w.wait(lambda: eng.start_check is not None or eng.guide is not None, 15)
            if eng.start_check:
                print("start check:", eng.start_check["items"], flush=True)
                time.sleep(1.5)
                overlay_shot(0)
                close_scratch_part()
                ok = w.wait(lambda: eng.guide is not None, 15)
                print("start check cleared by itself:", ok, flush=True)
                w.rows.append({"n": 0, "title": "start check", "items": eng.start_check and eng.start_check["items"], "auto": ok})
        if args.start > 1:
            w.wait(lambda: eng.guide is not None, 15)
            d.front()
            if not args.as_is:
                d.keys("Esc", settle=0.4)
                d.keys("Esc", settle=0.4)
            if not args.as_is and re.search(r"\[Sketch\d+ of", d.win().title):      # an empty sketch from where the last run stopped
                d.click(2439, 215, settle=1.5)
            if eng.current != args.start:
                eng.ws.send(json.dumps({"type": "jump", "n": args.start}))
                w.wait(lambda: eng.current == args.start, 8)
        steps = w.plan()
        for n in range(args.start, args.to + 1):
            if n not in steps:
                print(f"no hands for step {n} yet; stopping", flush=True)
                break
            w.step(n, steps[n])
        rows = [r for r in w.rows if r["n"]]
        print("\nauto:", sum(1 for r in rows if r.get("auto") or r.get("already")), "of", len(rows),
              "| not auto:", [r["n"] for r in rows if not (r.get("auto") or r.get("already"))], flush=True)
        return 0
    finally:
        eng.stop()


if __name__ == "__main__":
    raise SystemExit(main())
