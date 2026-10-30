"""Overlay check (Windows): the P2-1 and P2-2 checks without hands, on the real overlay, engine and VS Code.

    py -m tests.accuracy.overlay_check

It resets the scratch folder (as landing_walk does), starts the engine (`--restart --record`) and the overlay
(`--force-renderer-accessibility`, so its card and buttons are visible to UI Automation), then:

  window      the overlay window's flags: always on top, click-through, never activated; covers the taskbar
  transparent screenshots with the overlay showing and hidden are identical away from what it draws
  buttons     card Next, bar Back / Skip / step list (row click jumps, » on a skipped row) / Show me
  hotkeys     Ctrl+Alt+→ ← S H M with VS Code focused
  click-thru  WindowFromPoint under the outline and elsewhere is VS Code; a real click there reaches VS Code
  focus       type in a test window, click the overlay's Next, type again: every letter lands, focus stays;
              plain H and S typed there never move the step
  walk        all 23 steps through the overlay: violet outline pixels on the engine's box, card not covering
              it, scheme dark; the step is done on that box (so a click through the outline must work) and
              Next is pressed with the hotkey
  restart     mid-walk the engine is killed ("Waiting for the engine" shows) and restarted: same step
  hide        hide, resume: same step

It takes the mouse and keyboard for ~4 min. Results: cache/screenshots/overlay/ (one PNG per step,
overlay.json). Left for a person: crispness at other display scalings, a second monitor.
"""
from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from engine import config
from engine.basefile.parse import parse_file
from engine.live.locate.vscode import VSCodeLocator, dump
from engine.schema.messages import Box
from tests.accuracy.landing_walk import (FOLDER, TUTORIAL, act, bring_front, click, click_into_editor, prepare,
                                        setup, top_window)

OUT = config.CACHE / "screenshots" / "overlay"
LOGS = config.LOGS
OVERLAY = "GhostGuide overlay"
VIOLET = (167, 139, 250)
VK = {"right": 0x27, "left": 0x25, "s": 0x53, "h": 0x48, "m": 0x4D}
u32 = ctypes.windll.user32 if sys.platform == "win32" else None

FOCUS_PROBE = r'''
import sys, tkinter as tk
out = sys.argv[1]
r = tk.Tk(); r.title("GG focus probe"); r.geometry("700x300+200+700")
t = tk.Text(r, font=("Consolas", 20)); t.pack(fill="both", expand=True); t.focus_set()
def save(_=None):
    open(out, "w", encoding="utf-8").write(t.get("1.0", "end-1c"))
t.bind("<KeyRelease>", save); r.after(200, lambda: (r.lift(), r.focus_force()))
r.mainloop()
'''


# ---------- engine / overlay processes ----------------------------------------------------------
class Rec:
    """Reads the engine's --record file as it grows."""

    def __init__(self, path: Path):
        self.path, self.msgs, self._pos = path, [], 0

    def poll(self) -> list[dict]:
        if self.path.exists():
            with self.path.open("rb") as f:
                f.seek(self._pos)
                data = f.read()
            end = data.rfind(b"\n") + 1                  # a line still being written waits for the next poll
            for line in data[:end].splitlines():
                if line.strip():
                    self.msgs.append(json.loads(line)["msg"])
            self._pos += end
        return self.msgs

    def last(self, kind: str):
        return next((m for m in reversed(self.poll()) if m["type"] == kind), None)

    def wait(self, pred, timeout: float = 6.0, since: int = 0):
        """First message at or after index `since` (see mark()) that matches; None on timeout."""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            for m in self.poll()[since:]:
                if pred(m):
                    return m
            time.sleep(0.15)
        return None

    def mark(self) -> int:
        return len(self.poll())

    def since(self, i: int) -> list[dict]:
        return self.poll()[i:]


def start_engine(restart: bool, tag: str):
    rec = LOGS / f"overlay_check-{tag}.jsonl"
    rec.unlink(missing_ok=True)
    cmd = [sys.executable, "-u", "-m", "engine", "play", str(TUTORIAL.relative_to(config.ROOT)), "--window",
           f"{FOLDER.name} - Visual Studio Code", "--record", str(rec)] + (["--restart"] if restart else [])
    p = subprocess.Popen(cmd, cwd=config.ROOT, stdout=(LOGS / f"overlay_check-{tag}.log").open("w"),
                         stderr=subprocess.STDOUT)
    return p, Rec(rec)


def start_overlay():
    return subprocess.Popen("npm start -- --force-renderer-accessibility", shell=True, cwd=config.ROOT / "overlay",
                            stdout=(LOGS / "overlay_check-overlay.log").open("w"), stderr=subprocess.STDOUT)


def kill(p) -> None:
    if p and p.poll() is None:
        subprocess.run(f"taskkill /PID {p.pid} /T /F", shell=True, capture_output=True)


# ---------- reading and driving the overlay -----------------------------------------------------
def ov_elements() -> list[dict]:
    return [e for e in dump(OVERLAY) if e.get("type") in ("Text", "Button") and e.get("rect") and e["rect"][2] > 0]


def find(name_start: str, els=None) -> dict | None:
    els = ov_elements() if els is None else els
    hits = [e for e in els if (e.get("name") or "").startswith(name_start)]
    return hits[0] if hits else None


def bar_rect(els) -> list[int] | None:
    parts = [e["rect"] for e in els if e["type"] == "Button" and (e["name"] or "")[:1] in "‹▴▾" or e["name"] in ("Skip »", "Hide")]
    return _union(parts) if parts else None


def card_rect(els, guide: dict | None) -> list[int] | None:
    """The card: its own texts (meta, title, why, …) and buttons, not the chips drawn at the target."""
    card = (guide or {}).get("card") or {}
    names = {v for k, v in card.items() if isinstance(v, str)} | {"Show me"}
    nx = card_next(els)
    parts = [e["rect"] for e in els if e["name"] in names] + ([nx["rect"]] if nx else [])
    return _union(parts) if parts else None


def card_next(els) -> dict | None:
    bar = bar_rect(els)
    nx = [e for e in els if e["type"] == "Button" and e["name"] == "Next ›" and not (bar and e["rect"][1] >= bar[1] - 4)]
    return nx[0] if nx else None


def _union(rects) -> list[int]:
    x0 = min(r[0] for r in rects); y0 = min(r[1] for r in rects)
    x1 = max(r[0] + r[2] for r in rects); y1 = max(r[1] + r[3] for r in rects)
    return [x0, y0, x1 - x0, y1 - y0]


def _intersects(a, b) -> bool:
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def press(get) -> bool:
    """Click an overlay button. `get` re-finds it (a name prefix, or a function returning the element): the
    card can move when its target does, so hover, look again, and click only once it has stayed put. Hover
    first anyway: the overlay only takes the mouse while the pointer is over a card or the bar."""
    import uiautomation as auto
    finder = (lambda: find(get)) if isinstance(get, str) else get
    el = finder()
    for _ in range(4):
        if el is None:
            return False
        x, y, w, h = el["rect"]
        auto.MoveTo(x + w // 2, y + h // 2, moveSpeed=3)
        time.sleep(0.35)
        again = finder()
        if again is not None and again["rect"] == el["rect"]:
            auto.Click(x + w // 2, y + h // 2)
            return True
        el = again
    return False


def hotkey(key: str) -> None:
    k = VK[key]
    for vk in (0x11, 0x12, k):
        u32.keybd_event(vk, 0, 0, 0)
    for vk in (k, 0x12, 0x11):
        u32.keybd_event(vk, 0, 2, 0)


def state(rec: Rec):
    return rec.last("state")


def wait_step(rec: Rec, n: int, since: int, timeout=6.0):
    return rec.wait(lambda m: m["type"] == "state" and m["current"] == n and not m["hidden"], timeout, since)


def grab():
    from PIL import ImageGrab
    return ImageGrab.grab(all_screens=True)


def lands(style: str, b: dict, vb) -> bool:
    """Did the violet the overlay drew end up on the engine's box? Each style draws differently:
    outline / click_type hug the box; beacon is a pulsing dot on its top-right corner (beacon.ts); ghost
    text starts on the box's line (multi-line code runs on below); path chips sit at the box and run on to
    the right."""
    if not vb:
        return False
    cx, cy = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
    vcx, vcy = (vb[0] + vb[2]) / 2, (vb[1] + vb[3]) / 2
    if style in ("outline", "click_type", "code_card"):
        return abs(vcx - cx) <= 12 and abs(vcy - cy) <= 12
    if style == "beacon":
        return abs(vcx - (b["x"] + b["w"])) <= 16 and abs(vcy - b["y"]) <= 16
    if style == "ghost_text":
        return abs(vb[1] - b["y"]) <= b["h"] and vb[0] < b["x"] + b["w"]
    return vb[0] <= cx <= vb[2] and vb[1] <= cy <= vb[3]


def outline_on_box(img, b: dict, tol=40) -> float:
    """Share of the expected outline border (4 px outside the box, ±3 px) that is violet. Testing the border
    itself, not 'any violet nearby', so the app's own purple syntax colours can't fake or spoil it."""
    px = img.convert("RGB").load()
    W, H = img.size
    x0, y0, x1, y1 = b["x"] - 4, b["y"] - 4, b["x"] + b["w"] + 4, b["y"] + b["h"] + 4

    def violet_near(x, y):
        return any(0 <= x + dx < W and 0 <= y + dy < H and all(abs(c - v) < tol for c, v in zip(px[x + dx, y + dy], VIOLET))
                   for dx in (-3, -2, -1, 0, 1, 2, 3) for dy in (-3, -2, -1, 0, 1, 2, 3) if dx == 0 or dy == 0)
    pts = [(x, y) for x in range(x0 + 8, x1 - 8, 6) for y in (y0, y1)] + \
          [(x, y) for y in range(y0 + 8, y1 - 8, 6) for x in (x0, x1)]
    return sum(violet_near(x, y) for x, y in pts) / max(1, len(pts))


def violet_bbox(img, region, tol=38):
    x0, y0, x1, y1 = (max(0, region[0]), max(0, region[1]), min(img.width, region[2]), min(img.height, region[3]))
    if x1 <= x0 or y1 <= y0:                              # box off the screen
        return None
    crop = img.crop((x0, y0, x1, y1)).convert("RGB")
    px = crop.load()
    xs, ys = [], []
    for j in range(crop.height):
        for i in range(crop.width):
            r, g, b = px[i, j]
            if abs(r - VIOLET[0]) < tol and abs(g - VIOLET[1]) < tol and abs(b - VIOLET[2]) < tol:
                xs.append(i); ys.append(j)
    if len(xs) < 20:
        return None
    return [x0 + min(xs), y0 + min(ys), x0 + max(xs), y0 + max(ys)]


# ---------- the checks --------------------------------------------------------------------------
def main(argv=None) -> int:
    if sys.platform != "win32":
        print("The overlay check needs Windows.")
        return 2
    from engine.dpi import make_dpi_aware
    make_dpi_aware()
    import uiautomation as auto
    from PIL import ImageDraw

    OUT.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    results: dict[str, dict] = {}
    walk: list[dict] = []

    def record(name: str, ok, **detail):
        results[name] = {"ok": ok, **detail}
        mark = {True: "ok  ", False: "FAIL", None: "n/a "}[ok]
        print(f"[{mark}] {name}" + (f"  {json.dumps(detail, ensure_ascii=False)[:180]}" if detail else ""))

    win, title = setup(FOLDER, fresh=True)
    eng, rec = start_engine(restart=True, tag="a")
    ov = start_overlay()
    probe = None
    try:
        g1 = rec.wait(lambda m: m["type"] == "guide" and m["step"]["n"] == 1 and m.get("box"), 25)
        ow = None
        for _ in range(40):
            ow = top_window(OVERLAY)
            if ow and find("Next ›"):
                break
            time.sleep(0.5)
        if not (g1 and ow):
            print("overlay or engine didn't come up; logs in", LOGS)
            return 1
        bring_front(win)
        park = (sw_ := u32.GetSystemMetrics(0)) // 2, u32.GetSystemMetrics(1) // 2   # off any card: the window
        auto.MoveTo(*park, moveSpeed=4)                   # is click-through only while the cursor isn't on one
        time.sleep(1.5)

        # ---- window ----
        h = ow.NativeWindowHandle
        ex = u32.GetWindowLongW(h, -20)
        r = ow.BoundingRectangle
        sw, sh = u32.GetSystemMetrics(0), u32.GetSystemMetrics(1)
        flags = {"topmost": bool(ex & 0x8), "click_through": bool(ex & 0x20), "layered": bool(ex & 0x80000),
                 "no_activate": bool(ex & 0x8000000)}
        covers = r.left <= 0 and r.top <= 0 and r.right >= sw and r.bottom >= sh
        record("window: on top, click-through, never activated, covers the taskbar", all(flags.values()) and covers,
               **flags, rect=[r.left, r.top, r.width(), r.height()], screen=[sw, sh])
        record("second monitor", None if u32.GetSystemMetrics(80) == 1 else False, monitors=u32.GetSystemMetrics(80),
               note="one monitor: nothing to check")

        # ---- transparent: same pixels with the overlay showing and hidden, away from what it draws ----
        els = ov_elements()
        shown = grab()
        k = rec.mark()
        hotkey("h")
        hid = rec.wait(lambda m: m["type"] == "state" and m["hidden"], 4, k)
        time.sleep(0.6)
        hidden_img = grab()
        avoid = [card_rect(els, g1), bar_rect(els), [g1["box"]["x"] - 20, g1["box"]["y"] - 20, g1["box"]["w"] + 40, g1["box"]["h"] + 40]]
        region = (900, 700, 1700, 1250)
        clear = not any(a and _intersects(a, [region[0], region[1], region[2] - region[0], region[3] - region[1]]) for a in avoid)
        from PIL import ImageChops
        diff = ImageChops.difference(shown.crop(region).convert("RGB"), hidden_img.crop(region).convert("RGB"))
        mean = sum(sum(px) for px in diff.getdata()) / (diff.width * diff.height * 3)
        record("transparent (desktop shows through, no sheet)", bool(hid) and clear and mean < 1.5,
               mean_pixel_diff=round(mean, 3), region=region)
        pill = find("GhostGuide paused")
        record("hide shows only the 'paused · Resume' pill", bool(pill) and not find("Next ›"), pill=bool(pill))
        k = rec.mark()
        hotkey("h")
        record("hotkey Ctrl+Alt+H hides and resumes on the same step", bool(hid) and bool(wait_step(rec, 1, k)))

        # ---- click-through ----
        bx = g1["box"]
        pt_outline = (bx["x"] + bx["w"] // 2, bx["y"] + bx["h"] // 2)
        tree = [e for e in dump(title) if e.get("type") == "TreeItem" and e.get("name") == "apps.svg"]
        pt_else = (tree[0]["rect"][0] + 60, tree[0]["rect"][1] + tree[0]["rect"][3] // 2) if tree else (300, 700)
        hits = {}
        import ctypes.wintypes as wt
        u32.WindowFromPoint.argtypes = [wt.POINT]
        u32.WindowFromPoint.restype = wt.HWND
        u32.GetAncestor.argtypes = [wt.HWND, ctypes.c_uint]
        u32.GetAncestor.restype = wt.HWND
        for name, (x, y) in (("outline", pt_outline), ("elsewhere", pt_else)):
            auto.MoveTo(x, y, moveSpeed=4)                # the cursor is there, as when a person clicks it
            time.sleep(0.15)
            root = u32.GetAncestor(u32.WindowFromPoint(wt.POINT(x, y)), 2)          # GA_ROOT
            hits[name] = (root or 0) == win.NativeWindowHandle
        bring_front(win)
        click(*pt_else)
        time.sleep(1.2)
        tabs = [e for e in dump(title) if e.get("type") == "TabItem" and "apps.svg" in (e.get("name") or "")]
        record("clicks pass through (under the outline and elsewhere VS Code gets them)", all(hits.values()) and bool(tabs),
               window_from_point=hits, real_click_opened_apps_svg=bool(tabs))
        for t in tabs:                                   # close the preview it opened, with its tab's close button
            tr = t["rect"]
            close = [e for e in dump(title) if e.get("type") == "Button" and (e.get("name") or "").startswith("Close")
                     and tr[0] <= e["rect"][0] <= tr[0] + tr[2] and tr[1] <= e["rect"][1] <= tr[1] + tr[3]]
            if close:
                cr = close[0]["rect"]
                click(cr[0] + cr[2] // 2, cr[1] + cr[3] // 2)
                time.sleep(0.6)

        # ---- buttons ----
        k = rec.mark()
        press(lambda: card_next(ov_elements()))
        ok_next = wait_step(rec, 2, k)
        marked = any(m["type"] == "mark" for m in rec.since(k))
        record("card Next › moves on (outline turns green first)", bool(ok_next) and marked, mark_sent=marked)
        time.sleep(0.6)
        k = rec.mark()
        press("‹ Back")
        record("bar ‹ Back", bool(wait_step(rec, 1, k)))
        time.sleep(1.2)                                   # step 1 has a target, so its card offers Show me
        k = rec.mark()
        sm_btn = find("Show me")
        if sm_btn:
            press("Show me")
        sm = rec.wait(lambda m: m["type"] == "show_me", 4, k)
        record("card Show me", bool(sm))
        time.sleep(1.5)
        k = rec.mark()
        press("Skip »")
        st = wait_step(rec, 2, k)
        record("bar Skip » (step 1 marked skipped)", bool(st) and st["statuses"][0] == "skipped")
        time.sleep(0.6)
        press("▴ Step")
        time.sleep(0.8)
        els = ov_elements()
        skipped_mark = any(e["name"] == "»" for e in els)
        row = find("Thumbnail link and image", els)
        k = rec.mark()
        if row:
            press("Thumbnail link and image")
        record("step list opens, shows » on the skipped row, a row click jumps", skipped_mark and bool(wait_step(rec, 5, k)),
               skipped_mark=skipped_mark)
        time.sleep(0.6)
        tog = find("▾ Step") or find("▴ Step")
        if tog and tog["name"].startswith("▾"):
            press(tog["name"])                           # close the list again
            time.sleep(0.5)

        # ---- hotkeys with VS Code focused ----
        bring_front(win)
        time.sleep(0.3)
        k = rec.mark(); hotkey("right"); r1 = wait_step(rec, 6, k)
        time.sleep(0.4); k = rec.mark(); hotkey("left"); r2 = wait_step(rec, 5, k)
        time.sleep(0.4); k = rec.mark(); hotkey("s"); r3 = wait_step(rec, 6, k)
        record("hotkeys Ctrl+Alt+→ / ← / S with VS Code focused", all((r1, r2, r3)), next=bool(r1), back=bool(r2), skip=bool(r3))
        k = rec.mark()
        hotkey("m")
        sm = rec.wait(lambda m: m["type"] == "show_me", 3, k)
        ov_log = (LOGS / "overlay_check-overlay.log").read_text(encoding="utf-8", errors="replace")
        taken = [ln for ln in ov_log.splitlines() if "hotkeys taken" in ln]
        record("hotkey Ctrl+Alt+M (Show me)", bool(sm), registered_by_another_app=taken[0] if taken else None)

        # ---- focus: typing never leaves the app, plain H / S never move the step ----
        probe_out = LOGS / "overlay_check-focus.txt"
        probe_out.unlink(missing_ok=True)
        probe = subprocess.Popen([sys.executable, "-c", FOCUS_PROBE, str(probe_out)])
        pw = None
        for _ in range(20):
            time.sleep(0.4)
            pw = top_window("GG focus probe")
            if pw:
                break
        bring_front(pw)
        pr = pw.BoundingRectangle
        click(pr.left + 200, pr.top + 150)               # into its text box
        time.sleep(0.8)
        before = state(rec)["current"]
        auto.SendKeys("ab", interval=0.05)
        k = rec.mark()
        press(lambda: card_next(ov_elements()))
        moved = wait_step(rec, before + 1, k)
        time.sleep(0.3)
        k = rec.mark()
        auto.SendKeys("cd hs", interval=0.05)
        time.sleep(1.2)
        text = probe_out.read_text(encoding="utf-8") if probe_out.exists() else ""
        fg_ok = u32.GetForegroundWindow() == pw.NativeWindowHandle
        after = state(rec)["current"]
        record("clicking the overlay never takes focus (typing continues in the app)",
               text == "abcd hs" and fg_ok and bool(moved), typed=text, foreground_kept=fg_ok)
        typed_moves = [m for m in rec.since(k) if m["type"] == "state" and m["current"] != before + 1]
        record("plain H and S typed in an app don't move the step", after == before + 1 and not typed_moves,
               step_before=before + 1, step_after=after)
        kill(probe)
        probe = None

        # ---- walk all steps through the overlay ----
        tut = parse_file(TUTORIAL)
        loc = VSCodeLocator(title)
        kill(eng)                                         # restart from step 1 (also: overlay waits, reconnects)
        time.sleep(2.5)
        waiting = find("Waiting for the engine")
        eng, rec = start_engine(restart=True, tag="b")
        up = wait_step(rec, 1, 0, 20)
        record("engine down: overlay says 'Waiting for the engine', reconnects by itself", bool(waiting) and bool(up))
        walk.clear()
        for step in tut.steps:
            n = step.n
            st = rec.last("state")
            if not (st and (st["current"] == n or rec.wait(lambda m: m["type"] == "state" and m["current"] == n, 8, rec.mark()))):
                walk.append({"n": n, "error": "engine not on this step"})
                print(f"  step {n}: engine isn't on it, stopping the walk")
                break
            prepare(step, win, title)
            time.sleep(1.4)                               # the engine re-locates every second
            g = rec.last("guide")
            if step.target.label == "Editor" and (g is None or g.get("box") is None):
                click_into_editor(win, title, (step.target.where or "").split(",")[0].strip())
                time.sleep(1.6)
                g = rec.last("guide")
            g = g if g and g["step"]["n"] == n else None
            time.sleep(0.5)
            img = grab()
            els = ov_elements()
            row = {"n": n, "action": step.action, "style": g and g["style"], "scheme": g and g["scheme"],
                   "box": g and g.get("box")}
            b = g and g.get("box")
            if b:
                vb = violet_bbox(img, (b["x"] - 40, b["y"] - 40, b["x"] + b["w"] + 40, b["y"] + b["h"] + 40))
                row["violet"] = vb
                if g["style"] in ("outline", "click_type", "code_card"):
                    row["outline_share"] = round(outline_on_box(img, b), 2)
                    row["lands"] = row["outline_share"] >= 0.8
                else:
                    row["lands"] = lands(g["style"], b, vb)
                c = card_rect(els, g)
                row["card_covers_target"] = bool(c and _intersects(c, [b["x"], b["y"], b["w"], b["h"]]))
            d = ImageDraw.Draw(img)
            if b and b["w"] > 0 and b["h"] > 0:
                d.rectangle([b["x"] - 1, b["y"] - 1, b["x"] + b["w"] + 1, b["y"] + b["h"] + 1], outline=(0, 255, 120), width=1)
            img.save(OUT / f"step{n:02d}.png")
            print(f"  step {n:2d} {step.action:9s} style={row['style']} scheme={row['scheme']} box={'yes' if b else 'no'}"
                  + (f" lands={row.get('lands')} card_covers={row.get('card_covers_target')}" if b else ""))
            if row["style"] == "code_card":           # Copy puts exactly the step's text on the clipboard
                auto.SetClipboardText("")
                pressed = press(lambda: next((e for e in ov_elements() if e["type"] == "Button" and e["name"] == "Copy"), None))
                time.sleep(0.4)
                want = str(step.params.get("value", "")).rstrip("\n")
                got = (auto.GetClipboardText() or "").replace("\r\n", "\n")      # Windows clipboard uses CRLF
                row["copy_ok"] = pressed and got == want and bool(find("Copied ✓"))
                if not row["copy_ok"]:
                    row["copy_detail"] = {"pressed": pressed, "got": got[:60], "want": want[:60]}
            act(step, Box(**b) if b else None, win, FOLDER, title, loc, row, OUT)
            if n == 12:                                   # restart mid-walk: resumes on the same step
                kill(eng)
                time.sleep(2.0)
                eng, rec = start_engine(restart=False, tag="c")
                row["resumed_same_step"] = bool(wait_step(rec, 12, 0, 20))
                record("engine restarted mid-way resumes on the same step", row["resumed_same_step"])
            if n == 13:
                k = rec.mark()
                hotkey("h"); time.sleep(0.8); hotkey("h")
                row["hide_resume_same_step"] = bool(wait_step(rec, 13, k, 4))
            bring_front(win)
            time.sleep(0.3)
            k = rec.mark()
            hotkey("right")
            rec.wait(lambda m: m["type"] == "state" and (m["current"] == n + 1 or m["finished"]), 5, k)
            walk.append(row)
        fin = rec.wait(lambda m: m["type"] == "state" and m["finished"], 6)
        targets = [w for w in walk if w.get("box")]
        record("walk: all 23 steps through the overlay, finished", bool(fin) and len(walk) == len(tut.steps),
               steps=len(walk))
        record("walk: outline drawn on the engine's box", all(w.get("lands") for w in targets),
               off=[w["n"] for w in targets if not w.get("lands")], with_target=len(targets))
        record("walk: card never covers the target", not any(w.get("card_covers_target") for w in targets),
               covered=[w["n"] for w in targets if w.get("card_covers_target")])
        cards = [w for w in walk if w.get("style") == "code_card"]
        record("walk: code card Copy puts the step's text on the clipboard", bool(cards) and all(w.get("copy_ok") for w in cards),
               failed=[w["n"] for w in cards if not w.get("copy_ok")], code_cards=len(cards))
        record("walk: scheme dark over VS Code", all(w.get("scheme") == "dark" for w in walk if w.get("scheme")),
               light=[w["n"] for w in walk if w.get("scheme") == "light"])
        no_target = [w["n"] for w in walk if not w.get("box") and w["action"] not in ("shortcut", "wait")]
        record("walk: every step that needs a target had one", not no_target, missing=no_target)
        if any("hide_resume_same_step" in w for w in walk):
            record("hide / resume mid-walk stays on the step", all(w.get("hide_resume_same_step", True) for w in walk))
    finally:
        kill(probe)
        kill(ov)
        kill(eng)

    (OUT / "overlay.json").write_text(json.dumps({"run_at": datetime.now().isoformat(timespec="seconds"),
                                                  "results": results, "walk": walk}, indent=2, ensure_ascii=False),
                                     encoding="utf-8")
    failed = [k for k, v in results.items() if v["ok"] is False]
    print(f"\n{len(results) - len(failed)} of {len(results)} ok" + (f"; failed: {failed}" if failed else ""))
    print(f"screenshots: {OUT}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
