"""The import window, on the real overlay and engine (Windows). Types into the window through UI Automation, so it doesn't
take the mouse for long. Run it after compiling, so its compile comes from the cache and costs nothing.

  1. a link to a site that refuses automatic reading: the window says so and offers the saved file,
  2. the path of a saved page: compiles (from the cache), shows the steps and the score,
  3. Play: the engine opens the compiled tutorial and sends step 1.

    py -m tests.accuracy.import_check --blocked-url https://… --saved sources/saved-page.html

Results: cache/screenshots/import/*.png and cache/logs/import_check.json.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from engine import config

OUT = config.CACHE / "screenshots" / "import"
TITLE = "GhostGuide: import a tutorial"
PORT = 8765


def wait(ok, s: float, every: float = 0.25):
    end = time.monotonic() + s
    while time.monotonic() < end:
        got = ok()
        if got:
            return got
        time.sleep(every)
    return ok()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--blocked-url", required=True)
    ap.add_argument("--saved", required=True)
    args = ap.parse_args(argv)
    if sys.platform != "win32":
        print("Needs Windows.")
        return 2

    import uiautomation as auto
    from websockets.sync.client import connect

    from engine.dpi import make_dpi_aware
    from engine.live import capture, windows
    make_dpi_aware()
    OUT.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "GG_LOCAL_APPMAPS": str(config.CACHE / "appmaps-check"), "PYTHONIOENCODING": "utf-8",
           "CHECK_MODELS": "off", "FINDER_VISION": "off"}
    logs = config.LOGS
    engine = subprocess.Popen([sys.executable, "-u", "-m", "engine", "play"], cwd=config.ROOT, env=env,
                              stdout=(logs / "import_check-engine.log").open("w", encoding="utf-8"), stderr=subprocess.STDOUT)
    overlay = None
    results: dict = {}
    messages: list[dict] = []
    try:
        ws = None
        for _ in range(60):
            try:
                ws = connect(f"ws://127.0.0.1:{PORT}", max_size=2 ** 22, ping_interval=None)
                break
            except OSError:
                time.sleep(0.5)
        if ws is None:
            raise SystemExit("the engine didn't start")

        def read():
            try:
                for raw in ws:
                    messages.append(json.loads(raw))
            except Exception:
                pass
        threading.Thread(target=read, daemon=True).start()

        overlay = subprocess.Popen("npm start -- --import --force-renderer-accessibility", shell=True, cwd=config.ROOT / "overlay",
                                   stdout=(logs / "import_check-overlay.log").open("w"), stderr=subprocess.STDOUT)
        win = wait(lambda: windows.find(TITLE), 90)
        if not win:
            raise SystemExit("the import window didn't open")
        time.sleep(2.0)
        control = auto.WindowControl(searchDepth=1, Name=TITLE)

        def shot(name: str) -> None:
            w = windows.find(TITLE)
            img = capture.window_region(w.hwnd, None) if w else None
            if img is not None:
                img.save(OUT / f"{name}.png")

        def edit(name: str):
            return control.EditControl(Name=name, searchDepth=20)

        def press(name: str) -> None:
            control.ButtonControl(Name=name, searchDepth=20).Invoke()

        def has_text(part: str) -> bool:
            def walk(c, depth=0):
                if depth > 20:
                    return False
                try:
                    if part.casefold() in (c.Name or "").casefold():
                        return True
                    return any(walk(k, depth + 1) for k in c.GetChildren())
                except Exception:
                    return False
            return walk(control)

        shot("1-empty")
        results["focusable"] = edit("Link to a video or article").Exists(5)

        # 1. a site that refuses
        edit("Link to a video or article").GetValuePattern().SetValue(args.blocked_url)
        press("Compile")
        results["blocked_message"] = bool(wait(lambda: has_text("doesn't allow automatic reading"), 40))
        shot("2-blocked")

        # 2. the saved page
        edit("Link to a video or article").GetValuePattern().SetValue(str(Path(args.saved).resolve()))
        press("Compile")
        results["done"] = bool(wait(lambda: any(m["type"] == "compile_done" for m in messages), 300))
        done = next((m for m in messages if m["type"] == "compile_done" and m.get("ok")), None)
        progress = [m for m in messages if m["type"] == "compile_progress"]
        results.update(progress_messages=len(progress), compile_ok=bool(done), cached=(done or {}).get("cached"),
                       steps=(done or {}).get("steps"), score=(done or {}).get("score"))
        results["score_shown"] = bool(wait(lambda: has_text("raw:"), 5))
        time.sleep(0.5)
        shot("3-compiled")

        # 3. Play
        before = len(messages)
        press("Play it")
        got = wait(lambda: next((m for m in messages[before:] if m["type"] in ("guide", "start_check")), None), 40)
        results["play_type"] = got and got["type"]
        results["play_state"] = next((m["tutorial"] for m in messages[before:] if m["type"] == "state"), None)
        results["window_closed"] = bool(wait(lambda: not windows.find(TITLE), 8))
        time.sleep(1.5)
        from PIL import ImageGrab
        ImageGrab.grab(all_screens=True).save(OUT / "4-playing.png")
    finally:
        for p in (overlay, engine):
            if p:
                subprocess.run(f"taskkill /PID {p.pid} /T /F", shell=True, capture_output=True)
    (logs / "import_check.json").write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(results, indent=1, ensure_ascii=False))
    need = ("blocked_message", "compile_ok", "score_shown", "play_type", "window_closed")
    return 0 if all(results.get(k) for k in need) else 1


if __name__ == "__main__":
    raise SystemExit(main())
