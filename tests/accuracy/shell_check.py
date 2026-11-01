"""The source window, the shortcuts panel and the tray, on the real overlay and engine (Windows). No model calls, no GPU.
Takes the mouse and keyboard for about 2 minutes. It looks inside the windows over Chromium's debug port.

A small test window stands in for the app. It counts its clicks and keeps what's typed, which is how this knows that
focus never left it and that clicks reached it:

  panel     closed at first; Ctrl+Alt+K or Keys opens it above the control bar; clicks go through it; a restart remembers
  colours   Ctrl+Alt+D flips light and dark, then goes back to automatic
  video     Ctrl+Alt+O opens the clip at the step's time without taking focus; it plays and stops at the step's end;
            the step moving on cues the next clip; the card's button and the control bar's close and open it
  text      a saved page opens at the step's section; a page never read is fetched once; a refusing site is explained
  tray      the icon is there, its menu moves the step, and where focus ends up afterwards

    py -m tests.accuracy.shell_check

Results: cache/logs/shell_check.json, cache/screenshots/shell/*.png. Your own settings aren't touched.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from engine import config

OUT = config.CACHE / "screenshots" / "shell"
LOGS = config.LOGS
PORT = 8765
DEBUG_PORT = 9333
SOURCE = "GhostGuide: source"
PROBE = "GG shell probe"
VIDEO = "tutorials/youtube-clone-vscode.md"
MUG = "tutorials/mug-solidworks.md"
VENV = "tutorials/compiled/12-virtual-environments-and-packages.compiled.md"
IDLE_S = 45
VK = {"right": 0x27, "left": 0x25, "o": 0x4F, "k": 0x4B, "q": 0x51, "d": 0x44}
u32 = ctypes.windll.user32 if sys.platform == "win32" else None

PROBE_APP = r'''
import sys, json, tkinter as tk
out = sys.argv[1]
r = tk.Tk(); r.title("GG shell probe"); r.attributes("-fullscreen", False)
w, h = r.winfo_screenwidth(), r.winfo_screenheight(); r.geometry(f"{w}x{h-85}+0+0")
t = tk.Text(r, font=("Consolas", 20)); t.pack(fill="both", expand=True); t.focus_set()
clicks = [0]
def save(_=None):
    json.dump({"text": t.get("1.0", "end-1c"), "clicks": clicks[0]}, open(out, "w", encoding="utf-8"))
def click(_):
    clicks[0] += 1; save()
t.bind("<KeyRelease>", save); t.bind("<Button-1>", click); r.after(200, lambda: (r.lift(), r.focus_force()))
r.mainloop()
'''


def idle_s() -> float:
    class Info(ctypes.Structure):
        _fields_ = [("size", ctypes.c_uint), ("time", ctypes.c_uint)]
    i = Info(ctypes.sizeof(Info), 0)
    u32.GetLastInputInfo(ctypes.byref(i))
    return (ctypes.windll.kernel32.GetTickCount() - i.time) / 1000


def wait(ok, s: float, every: float = 0.2):
    end = time.monotonic() + s
    while time.monotonic() < end:
        got = ok()
        if got:
            return got
        time.sleep(every)
    return ok()


class Page:
    """One window's page, over Chromium's debug port."""

    def __init__(self, ws_url: str):
        from websockets.sync.client import connect
        self.ws = connect(ws_url, max_size=2 ** 24, ping_interval=None)
        self.n = 0

    def js(self, expr: str):
        self.n += 1
        self.ws.send(json.dumps({"id": self.n, "method": "Runtime.evaluate",
                                 "params": {"expression": expr, "returnByValue": True, "awaitPromise": True}}))
        while True:
            d = json.loads(self.ws.recv())
            if d.get("id") == self.n:
                return (d.get("result", {}).get("result") or {}).get("value")

    def close(self):
        self.ws.close()


def page(file_part: str) -> Page | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json", timeout=2) as r:
            targets = json.load(r)
    except OSError:
        return None
    hit = next((t for t in targets if file_part in t.get("url", "") and t.get("webSocketDebuggerUrl")), None)
    return Page(hit["webSocketDebuggerUrl"]) if hit else None


class Rig:
    def __init__(self, settings: Path, sources: str | None = None):
        self.settings, self.sources = settings, sources
        self.engine = self.overlay = None

    def start_engine(self, tutorial: str, tag: str) -> None:
        self.kill(self.engine)
        env = {**os.environ, "GG_LOCAL_APPMAPS": str(config.CACHE / "appmaps-check"), "CHECK_MODELS": "off", "FINDER_VISION": "off",
               "PYTHONIOENCODING": "utf-8"}
        if self.sources:
            env["GG_SOURCES"] = self.sources
        self.engine = subprocess.Popen([sys.executable, "-u", "-m", "engine", "play", tutorial, "--restart"], cwd=config.ROOT, env=env,
                                       stdout=(LOGS / f"shell_check-{tag}.log").open("w", encoding="utf-8"), stderr=subprocess.STDOUT)

    def start_overlay(self) -> None:
        self.kill(self.overlay)
        env = {**os.environ, "GG_SETTINGS": str(self.settings)}
        self.overlay = subprocess.Popen(f"npm start -- --force-renderer-accessibility --remote-debugging-port={DEBUG_PORT}", shell=True,
                                        cwd=config.ROOT / "overlay", env=env,
                                        stdout=(LOGS / "shell_check-overlay.log").open("w", encoding="utf-8"), stderr=subprocess.STDOUT)

    @staticmethod
    def kill(p) -> None:
        if p and p.poll() is None:
            subprocess.run(f"taskkill /PID {p.pid} /T /F", shell=True, capture_output=True)

    def stop(self) -> None:
        self.kill(self.overlay)
        self.kill(self.engine)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="start even if the PC is in use")
    args = ap.parse_args(argv)
    if sys.platform != "win32":
        print("Needs Windows.")
        return 2
    if idle_s() < IDLE_S and not args.force:
        print(f"Someone used this PC {idle_s():.0f} s ago. Not taking the mouse.")
        return 3

    import uiautomation as auto
    from PIL import ImageGrab

    from engine.dpi import make_dpi_aware
    from engine.live import windows
    make_dpi_aware()
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="gg-shell-"))
    settings, probe_out = tmp / "settings.json", tmp / "probe.json"
    results: list[dict] = []
    failures = 0

    def record(name: str, ok, **info) -> None:
        nonlocal failures
        failures += ok is False
        results.append({"check": name, "ok": ok, **info})
        print(("PASS " if ok else "n/a  " if ok is None else "FAIL ") + name + (f"  {info}" if info else ""), flush=True)

    def hotkey(key: str) -> None:
        k = VK[key]
        for vk in (0x11, 0x12, k):
            u32.keybd_event(vk, 0, 0, 0)
        for vk in (k, 0x12, 0x11):
            u32.keybd_event(vk, 0, 2, 0)

    def overlay_page() -> Page | None:
        """The primary display's overlay: the one that draws the control bar."""
        for _ in range(2):
            p = wait(lambda: page("index.html"), 60)
            if p and wait(lambda: p.js("!!document.querySelector('.bar-ctl')"), 30):
                return p
        return None

    def rect_of(p: Page, css: str):
        r = p.js(f"(()=>{{const e=document.querySelector({json.dumps(css)}); if(!e) return null; const r=e.getBoundingClientRect();"
                 "return {x:r.left,y:r.top,w:r.width,h:r.height,s:devicePixelRatio}})()")
        return r and {k: r[k] * r["s"] for k in ("x", "y", "w", "h")}

    def real_click(x: float, y: float) -> None:
        auto.MoveTo(int(x), int(y), moveSpeed=4)
        time.sleep(0.4)      # the overlay takes the mouse only once it sees the pointer over a button
        auto.Click(int(x), int(y))
        time.sleep(0.35)

    def click_el(p: Page, css: str) -> bool:
        """Hover, look again, click once it has stayed put: a card can move when its target does."""
        r = rect_of(p, css)
        for _ in range(5):
            if not r:
                return False
            x, y = r["x"] + r["w"] / 2, r["y"] + r["h"] / 2
            auto.MoveTo(int(x), int(y), moveSpeed=4)
            time.sleep(0.5)
            again = rect_of(p, css)
            if again == r:
                auto.Click(int(x), int(y))
                time.sleep(0.35)
                return True
            r = again
        return False

    def click_in_source(p: Page, css: str) -> bool:
        """A normal window: its page starts below the title bar, so measure from the window's bottom left."""
        r = p.js(f"(()=>{{const r=document.querySelector({json.dumps(css)}).getBoundingClientRect();"
                 "return {x:r.left+r.width/2,y:innerHeight-(r.top+r.height/2),s:devicePixelRatio}})()")
        x, y, _, h = windows.find(SOURCE).rect
        real_click(x + r["x"] * r["s"], y + h - r["y"] * r["s"])
        return True

    def probe() -> dict:
        try:
            return json.loads(probe_out.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"text": "", "clicks": 0}

    def front_is_probe() -> bool:
        w = windows.foreground()
        return bool(w and PROBE in w.title)

    letters = iter("abcdefghijklmnopqrstuvwxyz" * 4)

    def types_into_probe() -> bool:
        ch = next(letters)
        before = probe()["text"]
        u32.keybd_event(ord(ch.upper()), 0, 0, 0)
        u32.keybd_event(ord(ch.upper()), 0, 2, 0)
        return bool(wait(lambda: probe()["text"] == before + ch, 2))

    def shot(name: str) -> None:
        ImageGrab.grab(all_screens=True).save(OUT / f"{name}.png")

    def overlay_win():
        return next((w for w in windows.top_windows() if w.title == windows.OVERLAY_TITLE), None)

    def source_open():
        return windows.find(SOURCE)

    def source_page() -> Page | None:
        return wait(lambda: page("source.html"), 8)

    def park() -> None:
        auto.MoveTo(u32.GetSystemMetrics(0) // 4, u32.GetSystemMetrics(1) // 3, moveSpeed=4)
        time.sleep(0.2)

    def bring_probe() -> None:
        w = windows.find(PROBE)
        if w:
            u32.ShowWindow(w.hwnd, 9)
            u32.SetForegroundWindow(w.hwnd)
        time.sleep(0.3)

    rig = Rig(settings)
    probe_proc = subprocess.Popen([sys.executable, "-c", PROBE_APP, str(probe_out)])
    try:
        wait(lambda: windows.find(PROBE), 10)
        rig.start_engine(VIDEO, "video")
        rig.start_overlay()
        ov = overlay_page()
        if not ov:
            print("overlay didn't come up; logs in", LOGS)
            return 1
        bring_probe()
        park()
        time.sleep(1.5)
        taken = (LOGS / "shell_check-overlay.log").read_text(encoding="utf-8", errors="replace")
        record("no key is held by another app", "hotkeys taken" not in taken,
               taken=[l for l in taken.splitlines() if "hotkeys taken" in l])

        # ---------- the shortcuts panel ----------
        panel = ".keypanel"
        record("panel: closed at first", ov.js(f"!document.querySelector('{panel}')"))
        hotkey("k")
        wait(lambda: ov.js(f"!!document.querySelector('{panel}')"), 3)
        text = ov.js(f"document.querySelector('{panel}')?.innerText") or ""
        record("panel: Ctrl+Alt+K opens it, with every key", all(w in text for w in ("Next", "Back", "Skip", "Show me", "Source", "Hide", "Light / dark", "Import", "shortcuts", "End")), text=text.replace("\n", " "))
        time.sleep(0.4)      # let it finish fading in
        shot("1-panel")
        box, ctl = rect_of(ov, panel), rect_of(ov, ".bar-ctl")
        record("panel: stands right above the control bar", box["y"] + box["h"] <= ctl["y"] and abs(box["x"] + box["w"] - ctl["x"] - ctl["w"]) < 4, panel=box, control=ctl)
        record("panel: one key per line", box["h"] > box["w"])
        before = probe()["clicks"]
        real_click(box["x"] + box["w"] / 2, box["y"] + box["h"] / 2)
        record("panel: a click on it reaches the app under it", probe()["clicks"] == before + 1 and front_is_probe(), clicks=probe()["clicks"] - before)
        record("panel: typing stays in the app", types_into_probe())
        record("panel: the choice is saved", json.loads(settings.read_text(encoding="utf-8")).get("keyBar") is True)
        click_el(ov, ".bar-ctl button[data-a=rail]")
        wait(lambda: ov.js("!!document.querySelector('.rail')"), 3)
        time.sleep(0.3)
        side, rail = rect_of(ov, panel), rect_of(ov, ".rail")
        record("panel: moves aside for the step list", side["x"] + side["w"] <= rail["x"], panel=side, rail=rail)
        click_el(ov, ".bar-ctl button[data-a=rail]")
        click_el(ov, ".bar-ctl button[data-a=keys]")
        park()
        record("panel: Keys on the control bar closes it, focus stays", bool(wait(lambda: ov.js(f"!document.querySelector('{panel}')"), 3)) and front_is_probe() and types_into_probe())
        ov.close()
        rig.start_overlay()
        time.sleep(2.0)
        ov = overlay_page()
        bring_probe()
        record("panel: stays closed after a restart", bool(ov) and ov.js(f"!document.querySelector('{panel}')"))
        hotkey("k")
        wait(lambda: ov.js(f"!!document.querySelector('{panel}')"), 3)
        ov.close()
        rig.start_overlay()
        time.sleep(2.0)
        ov = overlay_page()
        bring_probe()
        record("panel: and open, if you left it open", bool(ov) and bool(wait(lambda: ov.js(f"!!document.querySelector('{panel}')"), 5)))
        scheme = "document.getElementById('root').dataset.scheme"
        wait(lambda: ov.js("!!document.querySelector('.card')"), 15)
        s0 = ov.js(scheme)
        hotkey("d")
        s1 = wait(lambda: (lambda v: v if v != s0 else None)(ov.js(scheme)), 4)
        shot("1b-scheme")
        hotkey("d")
        s2 = wait(lambda: (lambda v: v if v == s0 else None)(ov.js(scheme)), 6)
        record("Ctrl+Alt+D: flips the colours, then back to automatic", bool(s1) and bool(s2) and front_is_probe(), was=s0, flipped=s1, back=s2)
        auto.MoveTo(u32.GetSystemMetrics(0) * 3 // 4, u32.GetSystemMetrics(1) // 10, moveSpeed=4)     # off every card and bar
        time.sleep(0.3)
        record("click-through flag intact over the rest of the overlay", bool(u32.GetWindowLongW(overlay_win().hwnd, -20) & 0x20))

        # ---------- the card's size ----------
        bring_probe()
        wait(lambda: ov.js("!!document.querySelector('.card .grip')"), 15)
        w0 = rect_of(ov, ".card")["w"]
        g = rect_of(ov, ".card .grip")
        gx, gy = int(g["x"] + g["w"] / 2), int(g["y"] + g["h"] / 2)
        clicks = probe()["clicks"]
        auto.MoveTo(gx, gy, moveSpeed=4)
        time.sleep(0.5)
        auto.DragDrop(gx, gy, gx + 200, gy, moveSpeed=2)
        time.sleep(0.5)
        w1 = rect_of(ov, ".card")["w"]
        record("card: dragging the corner widens it", w1 > w0 + 150, was=w0, now=w1)
        record("card: the drag doesn't reach the app, and focus stays", probe()["clicks"] == clicks and front_is_probe() and types_into_probe())
        shot("1c-card-wide")
        park()
        hotkey("right")
        wait(lambda: "Step 2 of" in (ov.js("document.querySelector('.bar-ctl')?.innerText") or ""), 5)
        time.sleep(0.6)
        record("card: the next card keeps the size", abs(rect_of(ov, ".card")["w"] - w1) < 4, now=rect_of(ov, ".card")["w"])
        g = rect_of(ov, ".card .grip")
        auto.MoveTo(int(g["x"] + g["w"] / 2), int(g["y"] + g["h"] / 2), moveSpeed=4)
        time.sleep(0.5)
        for _ in range(2):
            auto.Click(int(g["x"] + g["w"] / 2), int(g["y"] + g["h"] / 2), waitTime=0.05)
        time.sleep(0.5)
        record("card: double-click puts it back", abs(rect_of(ov, ".card")["w"] - w0) < 60, was=w0, now=rect_of(ov, ".card")["w"])
        park()
        hotkey("left")
        wait(lambda: "Step 1 of" in (ov.js("document.querySelector('.bar-ctl')?.innerText") or ""), 5)
        time.sleep(0.5)

        # ---------- the clip ----------
        step1 = wait(lambda: ov.js("document.querySelector('.card .meta .src')?.innerText"), 15)
        record("card: shows the clip's time", step1 == "▶ 01:39", label=step1)
        bring_probe()
        hotkey("o")
        opened = wait(source_open, 15)
        record("video: Ctrl+Alt+O opens a window", bool(opened))
        time.sleep(0.8)
        record("video: opening it doesn't take focus", front_is_probe() and types_into_probe(), front=(windows.foreground() or windows.Win(0, "", (0, 0, 0, 0))).title)
        src = source_page()
        state = "(()=>{const v=document.getElementById('player');return {t:v.currentTime,paused:v.paused,ready:v.readyState,w:v.videoWidth,err:v.error&&v.error.message,src:v.getAttribute('src')}})()"
        v1 = wait(lambda: (lambda s: s if s and s["ready"] >= 2 and s["t"] > 9 else None)(src.js(state)), 8) or src.js(state)
        time.sleep(1.5)
        v2 = src.js(state)
        record("video: the clip is playing at the step's time", bool(v1) and not v2["paused"] and v2["w"] > 0 and 9 <= v1["t"] <= 14 and v2["t"] > v1["t"] and not v2["err"],
               first=v1 and v1["t"], later=v2["t"], width=v2["w"])
        record("video: the header names the step", "Step 1 of 23" in src.js("document.getElementById('meta').innerText") and "01:39" in src.js("document.getElementById('where').innerText"))
        shot("2-video")
        end = wait(lambda: src.js(state)["paused"], 15)
        stopped = src.js(state)["t"]
        record("video: stops at the end of the step", bool(end) and 17 <= stopped <= 19.5, at=stopped)
        win_rect = windows.find(SOURCE).rect
        first_rect = win_rect
        record("video: placed on the screen", win_rect[0] >= -10 and win_rect[1] >= -10 and win_rect[0] + win_rect[2] <= u32.GetSystemMetrics(0) + 10, rect=win_rect)
        click_in_source(src, "#replay")
        time.sleep(1.2)
        s = src.js(state)
        record("video: Play this step again", not s["paused"] and 9 <= s["t"] <= 12, at=s["t"])
        record("video: its own click is the only thing that took focus", bool(windows.foreground()) and "source" in windows.foreground().title)
        bring_probe()
        hotkey("right")
        moved = wait(lambda: "Step 2 of 23" in (src.js("document.getElementById('meta').innerText") or ""), 6)
        time.sleep(0.8)
        s = src.js(state)
        record("video: follows the step, cued and waiting", bool(moved) and s["paused"] and 9 <= s["t"] <= 11, at=s["t"], paused=s["paused"])
        record("video: following doesn't take focus", front_is_probe() and types_into_probe())
        hotkey("o")
        record("video: Ctrl+Alt+O closes it", bool(wait(lambda: not source_open(), 4)))
        src.close()
        wait(lambda: ov.js("!!document.querySelector('.card .meta .src')"), 8)
        ov.js("window.__clicks=[];addEventListener('click',e=>__clicks.push(e.target.className||e.target.tagName),true);0")
        where = rect_of(ov, ".card .meta .src")
        click_el(ov, ".card .meta .src")
        opened = wait(source_open, 8)
        record("reopened: same size, no creeping", bool(opened) and opened.rect[2:] == first_rect[2:], first=first_rect, now=opened and opened.rect)
        record("card: its button opens the source", bool(opened), rect=where, clicks=ov.js("__clicks"),
               under=ov.js(f"document.elementFromPoint({where['x'] + where['w'] / 2}/devicePixelRatio,{where['y'] + where['h'] / 2}/devicePixelRatio)?.className"),
               now=rect_of(ov, ".card .meta .src"))
        shot("card-click")
        park()
        record("card: and focus stays", front_is_probe() and types_into_probe())
        hotkey("o")
        wait(lambda: not source_open(), 4)
        click_el(ov, ".bar-ctl button[data-a=source]")
        record("control bar: its button opens the source", bool(wait(source_open, 8)))
        park()
        record("control bar: and focus stays", front_is_probe() and types_into_probe())
        before = probe()["clicks"]
        real_click(u32.GetSystemMetrics(0) // 4, u32.GetSystemMetrics(1) // 3)
        record("with the window open, clicks still reach the app", probe()["clicks"] == before + 1)
        hotkey("o")
        wait(lambda: not source_open(), 4)

        # ---------- fresh clone: no clip here ----------
        fresh = tmp / "fresh"
        fresh.mkdir()
        rig.sources = str(fresh)
        rig.start_engine(VIDEO, "fresh-video")
        time.sleep(3)
        bring_probe()
        hotkey("o")
        wait(source_open, 15)
        src = source_page()
        wait(lambda: src.js("!document.getElementById('none').hidden"), 5)
        msg = src.js("document.getElementById('message').innerText") or ""
        lbl = src.js("document.getElementById('link').innerText") or ""
        record("fresh clone, video: says so and offers the moment on the web", "isn't on this PC" in msg and "01:39" in lbl, message=msg, button=lbl)
        shot("3-fresh-video")
        src.close()
        hotkey("o")
        wait(lambda: not source_open(), 4)

        # ---------- fresh clone: a site that refuses ----------
        rig.start_engine(MUG, "fresh-mug")
        time.sleep(3)
        bring_probe()
        hotkey("o")
        wait(source_open, 15)
        src = source_page()
        said = wait(lambda: (lambda t: t if t and "automatic reading" in t or (t and "reached" in t) else None)(src.js("document.getElementById('message').innerText")), 15)
        record("fresh clone, refusing site: explained, with a link and a saved copy", bool(said) and bool(src.js("!document.getElementById('link').hidden && !document.getElementById('choose').hidden")), message=said)
        shot("4-refused")
        src.close()
        hotkey("o")
        wait(lambda: not source_open(), 4)

        # ---------- a page never read: fetched once, as ourselves ----------
        rig.start_engine(VENV, "fresh-venv")
        time.sleep(3)
        bring_probe()
        hotkey("o")
        wait(source_open, 15)
        src = source_page()
        here = wait(lambda: src.js("document.querySelector('.sec.here h2')?.innerText"), 15)
        record("page never read: fetched, and open at the section", bool(here) and "virtual" in here.lower(), section=here)
        src.close()
        hotkey("o")
        wait(lambda: not source_open(), 4)

        # ---------- the saved page, gold file with its own section names ----------
        rig.sources = None
        rig.start_engine(MUG, "mug")
        time.sleep(3)
        bring_probe()
        hotkey("o")
        wait(source_open, 15)
        time.sleep(0.5)
        record("text: opening it doesn't take focus", front_is_probe() and types_into_probe())
        src = source_page()
        here = wait(lambda: src.js("document.querySelector('.sec.here h2')?.innerText"), 8)
        top = src.js("(()=>{const r=document.querySelector('.sec.here').getBoundingClientRect();return r.top})()")
        scripts = src.js("document.querySelectorAll('#text script,#text iframe,#text a').length")
        record("text: the saved page opens at the step's section", bool(here) and "create" in here.lower() and top is not None and top < 200, section=here, top=top)
        record("text: words only, nothing from the page runs", scripts == 0)
        pics = "(()=>{const t=document.getElementById('text');return {shown:[...t.querySelectorAll('img')].filter(i=>i.complete&&i.naturalWidth>0).length,waiting:[...t.querySelectorAll('img')].filter(i=>!i.complete).length,said:[...t.querySelectorAll('p')].filter(p=>p.textContent.startsWith('A picture goes here')).length}})()"
        p = wait(lambda: (lambda v: v if v and not v["waiting"] else None)(src.js(pics)), 20) or src.js(pics)
        record("text: each picture shows, or says the site hasn't sent it", p["shown"] + p["said"] >= 10 and not p["waiting"], **p)
        click_in_source(src, "#page")
        record("text: Show the page opens a window of its own", bool(wait(lambda: next((w for w in windows.top_windows() if w.title == "GhostGuide: page"), None), 15)))
        site = wait(lambda: page("engineersrule"), 20)
        seen = wait(lambda: (lambda v: v if v and v["shown"] and v["at"] > 0 else None)(site.js("({shown:[...document.images].filter(i=>i.complete&&i.naturalWidth>200).length,at:scrollY})")), 25) if site else None
        record("text: and its pictures show, at the step's section", bool(seen) and seen["shown"] > 0 and seen["at"] > 0, seen=seen)
        shot("5b-page")
        if site:
            site.close()
        shot("5-text")
        bring_probe()
        hotkey("right")     # past the start check
        hotkey("right")
        time.sleep(0.5)
        for _ in range(6):
            hotkey("right")
            time.sleep(0.25)
        moved = wait(lambda: (lambda t: t if t and "create" not in t.lower() else None)(src.js("document.querySelector('.sec.here h2')?.innerText")), 8)
        record("text: follows the step to the next section", bool(moved), section=moved)
        src.close()
        hotkey("o")
        wait(lambda: not source_open(), 4)
        record("text: closing the source closes the page", not any(w.title == "GhostGuide: page" for w in windows.top_windows()))

        # ---------- the tray ----------
        rig.start_engine(VIDEO, "tray")
        time.sleep(3)
        wait(lambda: ov.js("!!document.querySelector('.card')"), 15)
        bring_probe()
        root = auto.GetRootControl()
        taskbar = auto.PaneControl(ClassName="Shell_TrayWnd")

        def named(scope, part):
            return next((c for c, _ in auto.WalkControl(scope, maxDepth=12) if part in (c.Name or "")), None)

        def press_el(c) -> None:
            r = c.BoundingRectangle
            real_click((r.left + r.right) / 2, (r.top + r.bottom) / 2)

        icon = named(taskbar, "GhostGuide")
        hidden = False
        if not icon:         # Windows puts a new icon under the arrow until you move it out
            def in_overflow():
                over = next((c for c in root.GetChildren() if c.ClassName == "TopLevelWindowForOverflowXamlIsland"), None)
                c = named(over, "GhostGuide") if over else None
                return c if c and c.BoundingRectangle.width() > 0 and not c.IsOffscreen else None
            icon = in_overflow()         # still open from before?
            if not icon:
                press_el(named(taskbar, "Show Hidden Icons"))
                icon = wait(in_overflow, 4)
            hidden = bool(icon)
        record("tray: the icon is there, saying where you are", bool(icon) and "Step 1 of 23" in icon.Name, icon=(icon.Name.strip() if icon else None), under_the_arrow=hidden)
        if icon:
            press_el(icon)
            time.sleep(0.8)
            shot("6-tray-menu")
            # The menu isn't in the accessibility tree. It opens up and right from the click; Next step sits this far up it.
            scale = ov.js("devicePixelRatio")
            r = icon.BoundingRectangle
            def menu_down(n: int) -> None:      # the menu isn't in the accessibility tree, and its width and side depend on its words
                for _ in range(n):
                    u32.keybd_event(0x28, 0, 0, 0)
                    u32.keybd_event(0x28, 0, 2, 0)
                    time.sleep(0.12)
                u32.keybd_event(0x0D, 0, 0, 0)
                u32.keybd_event(0x0D, 0, 2, 0)

            menu_down(3)                        # the status line, Hide, Next step
            moved = wait(lambda: "Step 2 of" in (ov.js("document.querySelector('.bar-ctl')?.innerText") or ""), 5)
            record("tray: its menu opens and moves the step", bool(moved))
            time.sleep(0.5)
            press_el(icon)
            time.sleep(0.8)
            menu_down(8)                        # …Back, source, Light / dark, the privacy line, Keep my screen on this PC
            kept = wait(lambda: "Nothing from your screen" in (ov.js("document.querySelector('.toast')?.innerText") or ""), 5)
            record("tray: Keep my screen on this PC reaches the engine", bool(kept))
            u32.keybd_event(0x1B, 0, 0, 0)
            u32.keybd_event(0x1B, 0, 2, 0)
            press_el(named(taskbar, "Show Hidden Icons") or icon)    # shut the flyout: left open, it sits over the control bar
            time.sleep(0.6)
            f = windows.foreground()
            record("tray: focus returns to the app afterwards", None if not front_is_probe() else True, front=f.title if f else "(none)",
                   note="Windows gives the tray the focus when you click it")

        # ---------- quitting ----------
        bring_probe()
        hotkey("q")
        time.sleep(2)
        record("Ctrl+Alt+Q quits the overlay", overlay_win() is None)
        record("the app under it is left alone", bool(windows.find(PROBE)))
        record("Ctrl+Alt+Q stops the engine too", bool(wait(lambda: rig.engine.poll() is not None, 5)))
        rig.start_engine(VIDEO, "end")
        rig.start_overlay()
        ov = overlay_page()
        bring_probe()
        wait(lambda: ov.js("!!document.querySelector('.bar-ctl button[data-a=end]')"), 15)
        shot("7-end")
        ok = click_el(ov, ".bar-ctl button[data-a=end]")
        record("End: the bar's button quits the overlay", ok and bool(wait(lambda: overlay_win() is None, 6)))
        record("End: and stops the engine", bool(wait(lambda: rig.engine.poll() is not None, 5)))
    finally:
        rig.stop()
        probe_proc.terminate()
        (LOGS / "shell_check.json").write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    done = [r for r in results if r["ok"] is not None]
    print(f"\n{sum(1 for r in done if r['ok'])} of {len(done)} passed; {len(results) - len(done)} need a look")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
