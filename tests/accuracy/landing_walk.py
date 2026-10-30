"""Landing check (Windows): walk the VS Code tutorial with no hands and save where each target was found.

For every step it
  1. does what a person would before looking (hovers the folder header for New File),
  2. asks the live locator (engine/live/locate/vscode.py) for the target,
  3. saves a screenshot of the VS Code window with that box drawn on it,
  4. does the step itself so the next one starts from the right state: real clicks on the located box for
     buttons, tabs, the tree and menus; typed names in the filename box; Ctrl+S for saves. Code is written
     to the file on disk (VS Code reloads a clean buffer), because Monaco's auto-close and Emmet make typed
     code unreliable, and the outline is what's being tested, not typing,
  5. checks the step's `verify` hint.
A click that lands wrong shows up as the next step failing (no filename box, wrong tab active).

It takes over the mouse and keyboard for about two minutes; don't touch them while it runs.

    py -m tests.accuracy.landing_walk                       # reset the scratch folder, all 23 steps
    py -m tests.accuracy.landing_walk --from 14 --no-reset  # carry on from the current state

Results: cache/screenshots/landing/stepNN.png and landing.json. The overlay isn't involved: it draws the
same physical-pixel box (P2-1 checks the overlay window itself).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from engine import config
from engine.basefile.parse import parse_file
from engine.live.locate.vscode import VSCodeLocator, dump, target_line
from tests.accuracy.uia_coverage import eval_uia_check

FOLDER = Path.home() / "Downloads" / "youtube-clone"
TUTORIAL = config.TUTORIALS / "youtube-clone-vscode.md"
OUT = config.CACHE / "screenshots" / "landing"
VIOLET = (167, 139, 250)
SETTINGS = {"editor.accessibilitySupport": "on", "editor.accessibilityPageSize": 2000,
            "liveServer.settings.port": 5501}
# What VS Code's Emmet makes of "!" + Tab (step 3), written directly.
EMMET_BANG = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
</head>
<body>

</body>
</html>"""


def window_title(folder: Path) -> str:
    return f"{folder.name} - Visual Studio Code"


def top_window(part: str):
    import uiautomation as auto
    for top in auto.GetRootControl().GetChildren():
        if part.casefold() in (top.Name or "").casefold():
            return top
    return None


def reset(folder: Path) -> None:
    backup = config.CACHE / "landing-backup" / datetime.now().strftime("%Y%m%d-%H%M%S")
    for name in ("index.html", "styles.css"):
        p = folder / name
        if p.exists():
            backup.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), backup / name)
    vs = folder / ".vscode" / "settings.json"
    vs.parent.mkdir(exist_ok=True)
    vs.write_text(json.dumps(SETTINGS, indent=2), encoding="utf-8")
    if backup.exists():
        print(f"moved the old index.html / styles.css to {backup}")


def open_vscode(folder: Path):
    win = top_window(window_title(folder))
    if win is None:
        subprocess.Popen(f'code -n "{folder}"', shell=True)
        for _ in range(40):
            time.sleep(0.5)
            win = top_window(window_title(folder))
            if win:
                break
    if win is None:
        raise SystemExit(f"no VS Code window titled '…{window_title(folder)}' appeared")
    bring_front(win)
    time.sleep(1.0)
    return win


def bring_front(win) -> None:
    """Make VS Code the foreground window, or stop: a click or key meant for VS Code must never land in
    another app. Windows refuses SetForegroundWindow from a background process unless a key was just
    pressed, hence the Alt tap."""
    import ctypes
    u32 = ctypes.windll.user32
    hwnd = win.NativeWindowHandle

    def front() -> bool:      # this window, or a popup it owns (a context menu); not another VS Code window
        fg = u32.GetForegroundWindow()
        return fg == hwnd or u32.GetAncestor(fg, 3) == hwnd        # GA_ROOTOWNER

    for _ in range(5):
        if front():
            return
        u32.keybd_event(0x12, 0, 0, 0)          # Alt down / up
        u32.keybd_event(0x12, 0, 2, 0)
        u32.ShowWindow(hwnd, 9)                 # SW_RESTORE
        u32.SetForegroundWindow(hwnd)
        time.sleep(0.4)
    if not front():
        raise SystemExit("VS Code won't come to the front; stopped so no input goes to another window")


def snap(win, box, label: str, path: Path) -> None:
    from PIL import ImageDraw, ImageGrab
    r = win.BoundingRectangle
    img = ImageGrab.grab(bbox=(max(0, r.left), max(0, r.top), r.right, r.bottom), all_screens=True)
    d = ImageDraw.Draw(img)
    ox, oy = max(0, r.left), max(0, r.top)
    if box is not None:
        x, y = box.x - ox, box.y - oy
        d.rectangle([x - 3, y - 3, x + box.w + 3, y + box.h + 3], outline=VIOLET, width=4)
        d.text((x, max(0, y - 22)), label, fill=VIOLET)
    else:
        d.text((20, 20), "NOT FOUND: " + label, fill=(255, 80, 80))
    img.save(path)


def write_code(folder: Path, step, editor_file: str) -> None:
    """Apply a `type` step to the file on disk at the line the locator reads from `where`."""
    p = folder / editor_file
    text = p.read_text(encoding="utf-8").replace("\r\n", "\n") if p.exists() else ""
    value = str(step.params.get("value", ""))
    if value == "!":
        text = EMMET_BANG
    elif "attribute" in (step.target.where or ""):
        n = target_line(text, step.target.where)
        lines = text.split("\n")
        i = lines[n - 1].rfind(">")
        lines[n - 1] = lines[n - 1][:i] + value + lines[n - 1][i:]
        text = "\n".join(lines)
    else:
        n = target_line(text, step.target.where, 1)
        lines = text.split("\n")
        indent = re.match(r"\s*", lines[n - 1] if n - 1 < len(lines) and lines[n - 1].strip()
                          else (lines[n - 2] if n >= 2 else "")).group(0)
        add = [(indent + ln if ln.strip() else ln) for ln in value.rstrip("\n").split("\n")]
        if n - 1 < len(lines) and not lines[n - 1].strip():
            lines[n - 1:n] = add                      # fill the empty line
        else:
            lines[n - 1:n - 1] = add
        text = "\n".join(lines)
    p.write_text(text, encoding="utf-8")


def check(step, title: str, wait_s: float = 4.0) -> bool | None:
    """The step's `verify` hints, re-read for a few seconds (VS Code reloads a file written on disk when it
    next looks, not instantly). A hint naming another window (Chrome) is read from that window."""
    checks = step.verify.uia_checks() if step.verify else []
    if not checks:
        return None
    end = time.monotonic() + wait_s
    while True:
        ok = True
        for c in checks:
            # a hint with no window may be about the browser (Live Server's address bar): look there too
            wins = [title] if c.window and "visual studio code" in c.window.casefold() else \
                [c.window] if c.window else [title, "Google Chrome"]
            hit = False
            for w in wins:
                els = dump(w)
                for el in els:
                    el.setdefault("window", c.window or w)
                hit = hit or eval_uia_check(c, els)
            ok = ok and hit
        if ok or time.monotonic() > end:
            return ok
        time.sleep(0.5)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--folder", default=str(FOLDER))
    ap.add_argument("--from", dest="start", type=int, default=1)
    ap.add_argument("--to", dest="end", type=int, default=None)
    ap.add_argument("--no-reset", action="store_true", help="keep the folder as it is")
    args = ap.parse_args(argv)
    if sys.platform != "win32":
        print("The landing check needs Windows (UI Automation).")
        return 2
    from engine.dpi import make_dpi_aware
    print(f"DPI awareness: {make_dpi_aware()}")
    import uiautomation as auto

    folder = Path(args.folder)
    fresh = not args.no_reset and args.start == 1
    if fresh:
        reset(folder)
    title = window_title(folder)
    win = open_vscode(folder)
    if fresh:
        # VS Code restores last session's tabs, now pointing at moved files: close every editor.
        bring_front(win)
        auto.SendKeys("{Ctrl}k")
        auto.SendKeys("w")
        time.sleep(1.0)
    for _ in range(20):          # the Explorer must be up before step 1
        if any((e.get("name") or "").startswith("Explorer Section:") for e in dump(title)):
            break
        time.sleep(0.5)
    loc = VSCodeLocator(title)
    tut = parse_file(TUTORIAL)
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for step in tut.steps:
        if step.n < args.start or (args.end and step.n > args.end):
            continue
        bring_front(win)
        time.sleep(0.3)
        t = step.target
        if norm_label(t.label).startswith("new file"):
            hdr = [e for e in dump(title) if e.get("type") == "Button" and (e.get("name") or "").startswith("Explorer Section:")]
            if hdr:
                x, y, w, h = hdr[0]["rect"]
                auto.MoveTo(x + w // 3, y + h // 2, moveSpeed=2)
                time.sleep(0.7)
        box, line = loc.locate(step)
        how = loc.last_how
        if how.startswith("click into the editor"):
            # as a person would before typing: click in the editor (below the code, so the caret goes to the end)
            body = [e["rect"] for e in dump(title) if e.get("type") == "Group" and e.get("name") == (t.where or "").split(",")[0].strip()]
            if body:
                x, y, w, h = body[0]
                bring_front(win)
                auto.Click(x + w // 2, y + h - 30)
                time.sleep(0.6)
                box, line = loc.locate(step)
                how = loc.last_how + " (after clicking into the editor)"
        path = OUT / f"step{step.n:02d}.png"
        snap(win, box, f"{step.n} {t.label}: {how}", path)
        print(f"[{step.n:2d}] {step.action:9s} {t.label!r:26s} → {how}  {box.model_dump() if box else ''} ({loc.last_seconds:.1f}s)")
        row = {"n": step.n, "action": step.action, "label": t.label, "how": how,
               "box": box.model_dump() if box else None, "seconds": round(loc.last_seconds, 2), "shot": str(path)}

        # do the step
        bring_front(win)
        if step.action == "click" and box is not None:
            auto.Click(*box.center)
            time.sleep(0.8)
        elif step.action == "type" and t.kind == "field" and "filename" in t.label.lower() and box is not None:
            auto.SendKeys(str(step.params["value"]), interval=0.02)
            auto.SendKeys("{Enter}")
            time.sleep(1.2)
        elif step.action == "type" and t.label == "Editor":
            fname = (t.where or "").split(",")[0].strip()
            write_code(folder, step, fname)
            time.sleep(0.6)
            bring_front(win)          # VS Code re-reads changed files when its window is active
            # whoever just typed has focus in the editor; Monaco only refreshes its UIA text while focused
            body = [e["rect"] for e in dump(title) if e.get("type") == "Group" and e.get("name") == fname]
            if body:
                x, y, w, h = body[0]
                auto.Click(x + w // 2, y + h - 30)
                time.sleep(0.4)
        elif step.action == "shortcut":
            auto.SendKeys("{Ctrl}s")
            time.sleep(0.6)
        elif step.action == "menu_path" and box is not None:
            auto.RightClick(*box.center)
            time.sleep(0.9)
            mbox, _ = loc.locate(step)
            snap(win, mbox, f"{step.n} menu: {loc.last_how}", OUT / f"step{step.n:02d}b.png")
            row["menu"] = {"how": loc.last_how, "box": mbox.model_dump() if mbox else None}
            print(f"     menu → {loc.last_how}")
            if mbox is not None and "menu item" in loc.last_how:
                bring_front(win)
                auto.Click(*mbox.center)
            else:
                auto.SendKeys("{Esc}")
            time.sleep(2.5)
            bring_front(win)
        elif step.action == "wait":
            time.sleep(1.0)
        else:
            row["skipped_action"] = True
        row["verify"] = check(step, title)
        if row["verify"] is not None:
            print(f"     verify: {'ok' if row['verify'] else 'FAILED'}")
        rows.append(row)

    found = [r for r in rows if r["box"] is not None]
    needs = [r for r in rows if r["action"] not in ("shortcut", "wait")]
    summary = {"steps": len(rows), "need_target": len(needs), "found": len([r for r in needs if r["box"]]),
               "estimated": [r["n"] for r in rows if "estimated" in r["how"]],
               "missed": [f"{r['n']}: {r['label']} ({r['how']})" for r in needs if not r["box"]],
               "verify_failed": [r["n"] for r in rows if r.get("verify") is False]}
    (OUT / "landing.json").write_text(json.dumps({"run_at": datetime.now().isoformat(timespec="seconds"),
                                                  "summary": summary, "steps": rows}, indent=2), encoding="utf-8")
    print("\n" + json.dumps(summary, indent=2))
    print(f"screenshots: {OUT}")
    return 0 if not summary["missed"] and not summary["verify_failed"] else 1


def norm_label(s: str) -> str:
    return " ".join(s.replace("…", "...").split()).casefold()


if __name__ == "__main__":
    raise SystemExit(main())
