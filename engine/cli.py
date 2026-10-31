"""python -m engine validate|record|spend|play|pin|appmap|compile|eval"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

from engine import config


def cmd_validate(args) -> int:
    from engine.basefile.validate import validate_file

    paths = sorted({p for pattern in args.paths for p in (glob.glob(pattern) or [pattern])})
    if not paths:
        print("no files given", file=sys.stderr)
        return 2
    failed = 0
    for path in paths:
        r = validate_file(path)
        status = "ok  " if r.ok else "FAIL"
        print(f"{status} {path} ({r.steps} steps, {len(r.errors)} errors, {len(r.warnings)} warnings)")
        for e in r.errors:
            print(f"     error: {e}")
        for w in r.warnings:
            print(f"     warn:  {w}")
        failed += not r.ok
    return 1 if failed else 0


def cmd_record(args) -> int:
    """One small Spark call through the client, so it can be replayed offline afterwards."""
    from engine.models.client import ModelClient

    client = ModelClient(mode=args.mode)
    reply = client.chat(
        model=args.model,
        messages=[{"role": "user", "content": args.prompt}],
        max_tokens=args.max_tokens,
        reasoning_effort=args.effort,
        tag="cli-record",
    )
    print(f"mode={client.mode} model={args.model} cost=${reply.cost_usd:.6f} cached={reply.from_cassette}")
    print(f"cassette: {reply.cassette_key}")
    print(reply.text)
    print(f"total logged spend: ${client.spent_usd():.4f} of ${client.budget_usd:.2f}")
    return 0


def cmd_spend(args) -> int:
    from engine.models.client import ModelClient

    c = ModelClient()
    print(f"spent ${c.spent_usd():.4f} of ${c.budget_usd:.2f} (log: {config.COST_LOG})")
    return 0


def _load_play(args):
    from engine.basefile.parse import parse_file
    from engine.live.locate.pinned import Pins, default_path
    from engine.live.player import Player
    from engine.live.scheme import pick_scheme
    from engine.live.session import Session

    tut = parse_file(args.tutorial)
    pins_path = Path(args.pins) if args.pins else default_path(args.tutorial)
    pins = Pins.load(pins_path)
    session = Session(tut, save_path=config.CACHE / "sessions" / (Path(args.tutorial).stem + ".json"))
    restored = False if args.restart else session.restore()
    if args.restart:
        session.save()
    override = None if args.scheme == "auto" else args.scheme
    locator = None
    if getattr(args, "locate", "pins") == "auto" and not getattr(args, "walk", None) and sys.platform == "win32":
        import uiautomation
        uiautomation.GetRootControl()      # started here: two worker threads racing to start it can fail
        locator = _resolver(tut, args)
    tracker = folder_fn = None
    if locator is not None and getattr(args, "check", "auto") == "auto":
        tracker, folder_fn = _tracker(tut, locator.window, args)
    player = Player(session, pins, scheme_fn=pick_scheme, scheme_override=override, pins_path=pins_path,
                    locator=locator, tracker=tracker, folder_fn=folder_fn, inputs=getattr(args, "_inputs", None))
    if tracker is not None:
        tracker.acted = player.acted_on
    if locator is not None and "visual studio code" not in tut.meta.app.casefold():
        _for_hard_apps(player, tut, locator, args)
    pinned = len(pins.steps)
    print(f"{tut.meta.title}: {session.of} steps, {pinned} pinned ({pins_path})"
          + (f", resuming at step {session.current}" if restored else ""))
    if locator is not None:
        print(f"  finding targets live in the '{locator.window}' window (app map → UIA → vision {'on' if getattr(locator, 'vision', None) else 'off'} → route); a pin overrides a step")
    if tracker is not None:
        models = "on" if tracker.ladder.glimmer or tracker.ladder.spark else "off"
        print(f"  checking each step (rules, then pixel diff; model checks {models}): it moves on by itself, Next always works")
    elif not pinned:
        print("  no pins yet: each card says how to pin its target as you go (hover, Ctrl+Alt+P twice)")
    return player


def _resolver(tut, args):
    """The finder chain for `play`: app map → UIA (VS Code's rule pack, SolidWorks', else names + aliases) → Spark
    vision (FINDER_VISION=on only) → route from the app map → Muse Wonder (same switch)."""
    from engine.appmap.store import AppMapStore
    from engine.live import capture, windows
    from engine.live.locate.menu import Hops, Wonder
    from engine.live.locate.resolver import GenericUIA, Resolver
    from engine.live.locate.vision import SparkVision, enabled

    vscode = "visual studio code" in tut.meta.app.casefold()
    solidworks = "solidworks" in tut.meta.app.casefold()
    window = args.window or ("Visual Studio Code" if vscode else tut.meta.app)
    version = _app_version(tut.meta.app)
    store = AppMapStore(tut.meta.app, version=version)
    if vscode:
        from engine.live.locate.vscode import VSCodeLocator
        stage = VSCodeLocator(window)
    elif solidworks:
        from engine.live.locate.solidworks import SolidWorksUIA
        stage = SolidWorksUIA(window, store)
    else:
        stage = GenericUIA(window, store)

    def find_window(part: str):
        w = windows.find(part)
        return w.rect if w else None

    def grab():
        """The app with its dialogs and open menus: (image, screen origin, display scale)."""
        w = windows.find(window)
        got = capture.with_popups(w.hwnd) if w else None
        return (got[0], got[1], windows.display_scale(w.hwnd)) if got else None

    def box_pixels(box):
        got = grab()
        return capture.crop(got[0], (box.x, box.y, box.w, box.h), got[1]) if got else None

    def looks(box, look) -> bool:
        now = box_pixels(box)
        return now is not None and bool(look) and capture.same_look(capture.look_of(now), look)

    def look_of(box):
        now = box_pixels(box)
        return capture.look_of(now) if now is not None else None

    def arrow(box):
        got = grab()
        return capture.dropdown_arrow(got[0], (box.x, box.y, box.w, box.h), got[1]) if got else None

    vision = wonder = None
    if enabled():
        vision = SparkVision(tut.meta.app, grab=grab, regions=solidworks)
        wonder = Wonder(tut.meta.app, version=version or "", grab=grab, store=store)
    print(f"  app map: {store.builtin_path or 'no built-in map'} + local {store.local_path}")

    def clicked(box, since: float) -> bool:
        recent = getattr(args, "_inputs", None)
        return recent is not None and any(e.t >= since and box.x <= e.x <= box.x + box.w and box.y <= e.y <= box.y + box.h
                                          for e in recent.clicks(within_s=60))

    return Resolver(stage, store, find_window, vision, wonder, Hops(clicked),
                    looks=looks if solidworks else None, look_of=look_of if solidworks else None, arrow=arrow if solidworks else None)


def _for_hard_apps(player, tut, locator, args) -> None:
    """What only the apps we can't read as well as VS Code get: the start check and Do it for me. The tracker's
    pictures take the whole app, since a click's result (a panel opening) shows far from what was clicked."""
    from engine.live import capture, windows
    from engine.live.execute import Executor
    from engine.live.startcheck import evaluate

    window = locator.window

    def start_items():
        titles = [w.title for w in windows.top_windows()     # the app's main window, not its dialogs
                  if w.title.startswith(window) and not windows.foreign_browser(w.title, window)]
        return evaluate(tut.meta.start_state, tut.meta.app, titles, windows.document_open)

    player.executor = Executor(window)
    player.start_items = start_items
    player.start_open = player.session.current == 1 and player.session.statuses[0] == "pending"
    if player.tracker is not None:
        def grab(step):
            w = windows.find(window)
            got = capture.with_popups(w.hwnd) if w else None
            return got[0] if got else None
        player.tracker.grab = grab
        player.tracker.diff_opts = {"width": 640, "share": 0.0003}     # a highlighted row is a tiny part of the whole app
        player.tracker.model_w = 1920                                  # sketch lines are thin: keep them visible

        def close_up(step, since, img):
            """A step on the canvas is judged near where you just clicked, if that shows the whole of it."""
            recent = getattr(args, "_inputs", None)
            w = windows.find(window)
            if step.target.kind not in ("canvas", "edge", "face") or recent is None or w is None:
                return None
            got = capture.with_popups(w.hwnd)
            pts = [(e.x, e.y) for e in recent.clicks(within_s=120) if e.t >= since]
            return capture.near_clicks(img, pts, got[1]) if got else None
        player.tracker.close_up = close_up


def _app_version(app: str):
    """The installed version, to pick the matching built-in map (VS Code: `code --version`, SolidWorks: from its
    window title)."""
    if "solidworks" in app.casefold():
        import re

        from engine.live import windows
        w = windows.find("SOLIDWORKS")
        m = re.search(r"\b(20\d\d)\b", w.title) if w else None
        return m.group(1) if m else "2026"
    if "visual studio code" not in app.casefold():
        return None
    import subprocess
    try:
        out = subprocess.run("code --version", shell=True, capture_output=True, text=True, timeout=10).stdout
        return out.split()[0] if out.strip() else None
    except Exception:
        return None


def _tracker(tut, app_window: str, args):
    """The step checker for `play`: rule checks on UIA dumps + files, the input watcher for settle, window
    captures for wait steps and the pixel diff. Model stages stay off (models/glimmer.py says why)."""
    from engine.live import capture, windows
    from engine.live.inputs import Watcher
    from engine.live.locate import uia
    from engine.live.verify import Ladder, Tracker
    from engine.models.glimmer import check_stages

    watcher = getattr(args, "_watcher", None) or Watcher().start()     # one per engine, kept when another tutorial opens
    args._watcher = watcher
    args._inputs = watcher.recent

    def dump(window: str) -> list[dict]:
        return uia.dump(window, every=window.casefold() not in app_window.casefold())

    def grab(step):
        # wait steps watch their window ("Browser"); others the app window around where the target was drawn
        w = windows.find(step.target.label) if step.target.kind == "window" else windows.find(app_window)
        if w is None:
            return None
        box = None if step.target.kind == "window" else getattr(args, "_player_box", lambda n: None)(step.n)
        return capture.window_region(w.hwnd, box)

    def folder_fn():
        if args.folder:
            return Path(args.folder)
        w = windows.find(app_window)
        return windows.vscode_folder(w.title) if w else None

    glimmer, spark = check_stages()
    return Tracker(tut, app_window, Path(args.folder) if args.folder else None, dump,
                   ladder=Ladder(glimmer=glimmer, spark=spark), idle_s=watcher.recent.idle_s, grab=grab), folder_fn


def _describe(msg) -> str:
    d = msg.to_wire()
    t = d["type"]
    if t == "guide":
        st, card = d["step"], d.get("card") or {}
        where = f" box={d['box']}" if d.get("box") else (" line" if d.get("line") else " (no target)")
        extra = {k: v for k, v in d.get("extra", {}).items() if k not in ("action", "label")}
        line = f"[{st['n']}/{st['of']}] {d['style']:<12} {d['scheme']:<5}{where} · {st['title']}"
        if card.get("detail"):
            line += f"\n      {card['detail']}"
        if extra:
            line += f"\n      extra: {json.dumps(extra, ensure_ascii=False)[:140]}"
        return line
    if t == "state":
        marks = "".join({"done": "✓", "skipped": "»", "pending": "·"}[s] for s in d["statuses"])
        return f"state: {marks}" + (" HIDDEN" if d["hidden"] else "") + (" FINISHED" if d["finished"] else "")
    return f"{t}: {json.dumps({k: v for k, v in d.items() if k != 'type'}, ensure_ascii=False)}"


CONSOLE_KEYS = {"n": "next", "b": "back", "s": "skip", "m": "show_me", "d": "do_it"}


def _score_lines(s: dict) -> list[str]:
    """What the import window shows: the score in plain words, raw first. The full report stays in `engine eval`."""
    lines = [f"Matches the hand-checked version: {s['raw']['f1']:.0%} ({s['raw']['matched']} of {s['raw']['gold_steps']} steps)"]
    if "fair" in s:
        lines.append(f"Allowing for what that version changed since the source: {s['fair']['f1']:.0%}")
    if s["details"]["typed_steps"]:
        lines.append(f"Typed text: {s['all_typed_text']:.0%} the same")
    lines.append(f"Steps the engine can check by itself: {s['verify_share']:.0%}")
    return lines


def _importer(msg, progress):
    """The import screen's compile: a link, a dropped file or pasted text. Runs on the compile worker thread."""
    from engine.compile.adapters import SourceBlocked, SourceError
    from engine.compile.eval import report
    from engine.compile.passes import CompileError
    from engine.compile.pipeline import Options, compile_tutorial
    from engine.models.client import BudgetExceeded, ModelError
    from engine.schema.messages import CompileDone

    src = msg.url or msg.file or msg.text
    if not src or not src.strip():
        return CompileDone(ok=False, error="Paste a link or some text, or drop a file.")
    try:
        r = compile_tutorial(src.strip(), Options(start=msg.start or None, end=msg.end or None), progress=progress)
    except SourceBlocked as e:
        return CompileDone(ok=False, error=str(e), blocked=True)
    except (SourceError, CompileError, ModelError) as e:
        return CompileDone(ok=False, error=str(e))
    except BudgetExceeded:
        return CompileDone(ok=False, error="This would pass the spending cap (BUDGET_USD), so it wasn't started.")
    return CompileDone(ok=True, path=str(r.path), title=r.title, steps=r.steps, cached=r.cached,
                       cost_usd=round(r.cost_usd, 4), score=_score_lines(r.score) if r.score else None, warnings=r.warnings)


def cmd_play(args) -> int:
    if not args.tutorial:
        return _serve(None, args)
    player = _load_play(args)
    if args.walk:
        return _walk(player, Path(args.walk), args.every, args.displays)
    if args.console:
        return _console(player)
    return _serve(player, args)


def _serve(player, args) -> int:
    import asyncio

    from engine.server import serve

    def box_of(n):
        b = current["player"].target(n)[0]
        return (b.x, b.y, b.w, b.h) if b else None

    current = {"player": player}
    args._player_box = box_of

    def opener(path: str):
        """The import screen's Play: this file, from its saved place, on the same watcher."""
        args.tutorial = path
        current["player"] = _load_play(args)
        return current["player"], getattr(args, "_inputs", None)

    print("start the overlay: cd overlay && npm start   (Ctrl+C here to stop)")
    try:
        asyncio.run(serve(player, port=args.port, record=Path(args.record) if args.record else None,
                          inputs=getattr(args, "_inputs", None), importer=_importer, opener=opener))
    except KeyboardInterrupt:
        pass
    return 0


def _console(player) -> int:
    """Drive the session from the terminal, no overlay: n next, b back, s skip, h hide/resume,
    j N jump, m show me, q quit. Prints what the overlay would be sent."""
    for msg in player.handle({"type": "hello"}) + player.refresh():
        print(_describe(msg))
    print("keys: n next · b back · s skip · h hide/resume · j N jump · m show me · q quit")
    while True:
        try:
            cmd = input("> ").strip().lower()
        except EOFError:
            break
        if cmd in ("q", "quit"):
            break
        if cmd in CONSOLE_KEYS:
            msg = {"type": CONSOLE_KEYS[cmd]}
        elif cmd == "h":
            msg = {"type": "resume" if player.session.hidden else "hide"}
        elif cmd.startswith("j"):
            try:
                msg = {"type": "jump", "n": int(cmd[1:].strip())}
            except ValueError:
                print("j needs a step number, e.g. j 5")
                continue
        else:
            continue
        for out in player.handle(msg) + player.refresh():     # refresh: the live locator, if any
            print(_describe(out))
    return 0


def _walk(player, out: Path, every_ms: int, displays: str) -> int:
    """Write a replay file for the overlay: hello, then Next every `every_ms` until the end, with a
    Show me on each step that has a target. Timestamps are simulated, so this runs instantly."""
    from engine.server import Recorder

    w, h = (int(v) for v in displays.lower().split("x"))
    rec = Recorder(out)
    t = 0
    hello = {"type": "hello", "displays": [{"id": 0, "x": 0, "y": 0, "w": w, "h": h, "primary": True}]}
    for msg in player.handle(hello):
        rec.write(msg, t)
    while not player.session.finished:
        if player.last_guide is not None and (player.last_guide.box or player.last_guide.line):
            for msg in player.handle({"type": "show_me"}):
                rec.write(msg, t + every_ms // 3)
        t += every_ms
        for msg in player.handle({"type": "next"}):
            rec.write(msg, t)
    rec.close()
    print(f"wrote {out} ({t / 1000:.0f} s of playback)")
    return 0


def cmd_pin(args) -> int:
    from engine.live.pinning import pin_interactive
    return pin_interactive(args.tutorial, args.pins, args.start, args.end)


def cmd_appmap(args) -> int:
    """Review the local app map and promote docs facts into the built-in one."""
    from engine.appmap.store import AppMapStore

    store = AppMapStore(args.app, version=args.version or _app_version(args.app))
    if args.action == "add":
        if not args.label:
            print("add needs a label", file=sys.stderr)
            return 2
        store.add_facts(args.label[0], aliases=args.alias or None, menu_path=args.menu or None,
                        shortcut=args.shortcut, source=args.source)
        print(f"added to the local layer: {store.local_path}")
        return 0
    if args.action == "promote":
        labels = args.label or list(store.reviewable())
        if not labels:
            print("nothing to promote")
            return 0
        path = store.promote(labels)
        print(f"promoted {', '.join(labels)} → {path} (docs facts only, no positions)")
        return 0
    print(f"built-in: {store.builtin_path or '(none yet)'}\nlocal:    {store.local_path}")
    for label in sorted(set(store.builtin.root) | set(store.local.root)):
        c = store.get(label)
        seen = f" · seen in {c.seen.window} at {list(c.seen.rel_box)}" if c.seen else ""
        facts = {k: v for k, v in c.model_dump(exclude={"seen"}).items() if v not in (None, [])}
        print(f"  {label}: {json.dumps(facts, ensure_ascii=False)}{seen}")
    todo = store.reviewable()
    if todo:
        print("waiting for review (promote copies these):")
        for label, facts in todo.items():
            print(f"  {label}: {json.dumps(facts, ensure_ascii=False)}")
    return 0


def cmd_compile(args) -> int:
    """A tutorial source → tutorials/compiled/*.md, scored when it has a gold file. Replies are recorded, so changing
    one prompt pays only for what that prompt touches."""
    from engine.compile.adapters import SourceError
    from engine.compile.eval import report
    from engine.compile.passes import CompileError
    from engine.compile.pipeline import Options, compile_tutorial
    from engine.models.client import BudgetExceeded, ModelClient, ModelError

    mode = args.mode or ("replay" if config.model_mode() == "replay" else "record")
    client = ModelClient(mode=mode)
    model = args.model or (config.SPARK_CONTRIBUTOR if args.tune else None)
    opts = Options(start=args.start, end=args.end, narration=args.narration, max_frames=args.max_frames, model=model,
                   enrich=not args.no_enrich, fresh=args.fresh, out=Path(args.out) if args.out else None,
                   gold=Path(args.gold) if args.gold else None, version=args.version)
    last = [""]

    def progress(stage: str, pct: float) -> None:
        if stage != last[0]:
            print(f"[{pct:4.0%}] {stage}", flush=True)
            last[0] = stage

    try:
        r = compile_tutorial(args.source, opts, client=client, progress=progress, log=print)
    except (SourceError, CompileError, BudgetExceeded, ModelError) as e:
        print(f"compile failed: {e}", file=sys.stderr)
        return 1
    print(f"{r.path}: {r.steps} steps, model {r.model}" + (" (from cache)" if r.cached else f", ${r.cost_usd:.4f} this run"))
    for w in r.warnings:
        print(f"  warn: {w}")
    if r.score:
        print(report(r.score))
    print(f"total logged spend: ${client.spent_usd():.4f} of ${client.budget_usd:.2f}")
    return 0


def cmd_eval(args) -> int:
    """Score a compiled file against a gold file. No model, so it's free and gives the same answer every time."""
    from engine.compile import eval as ev

    s = ev.score_files(args.compiled, args.gold)
    print(json.dumps(s, indent=1, ensure_ascii=False) if args.json else ev.report(s))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m engine")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="check base .md files against the schema and rules")
    v.add_argument("paths", nargs="+")
    v.set_defaults(func=cmd_validate)

    r = sub.add_parser("record", help="make one model call (records it in record mode, replays it in replay mode)")
    r.add_argument("--model", default=config.SPARK)
    r.add_argument("--prompt", default="Reply with exactly: GhostGuide ready.")
    r.add_argument("--max-tokens", type=int, default=256, help="reasoning counts toward this too")
    r.add_argument("--effort", default="minimal", help="reasoning_effort (Spark always reasons)")
    r.add_argument("--mode", choices=config.MODEL_MODES, default=None, help="overrides MODEL_MODE")
    r.set_defaults(func=cmd_record)

    s = sub.add_parser("spend", help="show logged model spend against the budget cap")
    s.set_defaults(func=cmd_spend)

    pl = sub.add_parser("play", help="play a tutorial on screen: engine side (start the overlay too)")
    pl.add_argument("tutorial", nargs="?", help="leave out to start empty and import one from the overlay")
    pl.add_argument("--pins", help="pinned boxes (default cache/pins/<tutorial>.yaml)")
    pl.add_argument("--port", type=int, default=8765)
    pl.add_argument("--record", help="also write every message sent to this .jsonl (overlay --replay format)")
    pl.add_argument("--scheme", choices=("auto", "light", "dark"), default="auto",
                    help="auto = from the pixels around the target (Windows), else the Windows theme")
    pl.add_argument("--restart", action="store_true", help="ignore saved progress, start at step 1")
    pl.add_argument("--locate", choices=("auto", "pins"), default="auto",
                    help="auto = find VS Code targets live with UIA (Windows), pins = hand pins only")
    pl.add_argument("--window", help='part of the app window title, e.g. "youtube-clone - Visual Studio Code"')
    pl.add_argument("--check", choices=("auto", "off"), default="auto",
                    help="auto = check each step and move on when it's done (smart Next); off = Next only")
    pl.add_argument("--folder", help="the tutorial's working folder for `file` checks (default: the folder open in VS Code)")
    pl.add_argument("--console", action="store_true", help="no overlay: drive it from the terminal")
    pl.add_argument("--walk", metavar="OUT.jsonl", help="write a replay file that steps through the whole tutorial")
    pl.add_argument("--every", type=int, default=3500, help="--walk: ms per step")
    pl.add_argument("--displays", default="1920x1080", help="--walk: screen size to report")
    pl.set_defaults(func=cmd_play)

    pn = sub.add_parser("pin", help="dev: pin each step's target box by hovering it (Windows)")
    pn.add_argument("tutorial")
    pn.add_argument("--pins", help="output (default cache/pins/<tutorial>.yaml); existing pins are kept")
    pn.add_argument("--from", dest="start", type=int, default=1)
    pn.add_argument("--to", dest="end", type=int, default=None)
    pn.set_defaults(func=cmd_pin)

    am = sub.add_parser("appmap", help="list the app map's two layers, add docs facts locally, promote reviewed ones")
    am.add_argument("action", choices=("list", "add", "promote"))
    am.add_argument("label", nargs="*", help="add: the control · promote: which ones (default: all waiting)")
    am.add_argument("--app", default="Visual Studio Code")
    am.add_argument("--version", help="default: the installed one (VS Code: code --version)")
    am.add_argument("--alias", action="append", help="add: another name for it (repeatable)")
    am.add_argument("--menu", action="append", help="add: one menu step of the route, in order (repeatable)")
    am.add_argument("--shortcut")
    am.add_argument("--source", help="add: the docs page the fact comes from")
    am.set_defaults(func=cmd_appmap)

    c = sub.add_parser("compile", help="turn a tutorial (link, video, saved page or text file) into a base .md file")
    c.add_argument("source")
    c.add_argument("--start", help="video: where the tutorial starts, e.g. 01:28")
    c.add_argument("--end", help="video: where it ends, e.g. 10:25")
    c.add_argument("--narration", choices=("auto", "captions", "transcribe"), default="auto")
    c.add_argument("--max-frames", type=int, default=150, help="video: most keyframes to read")
    c.add_argument("--tune", action="store_true", help="use Spark 1.3 Contributor (cheaper; Meta may train on what's sent)")
    c.add_argument("--model", help="overrides the model (default COMPILE_MODEL, else Spark 1.3)")
    c.add_argument("--no-enrich", action="store_true", help="skip the docs lookup")
    c.add_argument("--fresh", action="store_true", help="ignore the compile cache and the kept video reading")
    c.add_argument("--out", help="output file (default tutorials/compiled/)")
    c.add_argument("--gold", help="gold file to score against (default: found by the source's URL)")
    c.add_argument("--version", help="the app version to look up in its docs")
    c.add_argument("--mode", choices=config.MODEL_MODES, help="default record; replay spends nothing")
    c.set_defaults(func=cmd_compile)

    e = sub.add_parser("eval", help="score a compiled tutorial against a gold file (free)")
    e.add_argument("compiled")
    e.add_argument("gold")
    e.add_argument("--json", action="store_true")
    e.set_defaults(func=cmd_eval)

    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")   # ✓ » on a cp1252 console
        except (AttributeError, ValueError):
            pass
    from engine.dpi import make_dpi_aware
    make_dpi_aware()
    return args.func(args)
