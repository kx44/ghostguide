"""python -m engine validate|record|spend|play|pin (compile/eval in phase 5)"""
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
        locator = _resolver(tut, args)
    tracker = folder_fn = None
    if locator is not None and getattr(args, "check", "auto") == "auto":
        tracker, folder_fn = _tracker(tut, locator.window, args)
    player = Player(session, pins, scheme_fn=pick_scheme, scheme_override=override, pins_path=pins_path,
                    locator=locator, tracker=tracker, folder_fn=folder_fn, inputs=getattr(args, "_inputs", None))
    if tracker is not None:
        tracker.acted = player.acted_on
    pinned = len(pins.steps)
    print(f"{tut.meta.title}: {session.of} steps, {pinned} pinned ({pins_path})"
          + (f", resuming at step {session.current}" if restored else ""))
    if locator is not None:
        print(f"  finding targets live in the '{locator.window}' window (app map → UIA → vision {'on' if getattr(locator, 'vision', None) else 'off'} → route); a pin overrides a step")
    if tracker is not None:
        print("  checking each step (rules, then pixel diff; model checks off): it moves on by itself, Next always works")
    elif not pinned:
        print("  no pins yet: each card says how to pin its target as you go (hover, Ctrl+Alt+P twice)")
    return player


def _resolver(tut, args):
    """The finder chain for `play`: app map → UIA (VS Code's rule pack, else names + aliases) → Spark vision
    (FINDER_VISION=on only) → route from the app map."""
    from engine.appmap.store import AppMapStore
    from engine.live import capture, windows
    from engine.live.locate.resolver import GenericUIA, Resolver
    from engine.live.locate.vision import SparkVision, enabled

    vscode = "visual studio code" in tut.meta.app.casefold()
    window = args.window or ("Visual Studio Code" if vscode else tut.meta.app)
    store = AppMapStore(tut.meta.app, version=_app_version(tut.meta.app))
    if vscode:
        from engine.live.locate.vscode import VSCodeLocator
        stage = VSCodeLocator(window)
    else:
        stage = GenericUIA(window, store)

    def find_window(part: str):
        w = windows.find(part)
        return w.rect if w else None

    vision = None
    if enabled():
        def grab():
            w = windows.find(window)
            img = capture.window(w.hwnd) if w else None
            if img is None:
                return None
            png, scale = capture.for_model(img)
            return png, scale, w.rect[:2]
        vision = SparkVision(tut.meta.app, grab=grab)
    print(f"  app map: {store.builtin_path or 'no built-in map'} + local {store.local_path}")
    return Resolver(stage, store, find_window, vision)


def _app_version(app: str):
    """The installed version, to pick the matching built-in map (VS Code: `code --version`)."""
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

    watcher = Watcher().start()
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


def cmd_play(args) -> int:
    player = _load_play(args)
    if args.walk:
        return _walk(player, Path(args.walk), args.every, args.displays)
    if args.console:
        return _console(player)
    import asyncio

    from engine.server import serve
    args._player_box = lambda n: (lambda b: (b.x, b.y, b.w, b.h) if b else None)(player.target(n)[0])
    print("start the overlay: cd overlay && npm start   (Ctrl+C here to stop)")
    try:
        asyncio.run(serve(player, port=args.port, record=Path(args.record) if args.record else None,
                          inputs=getattr(args, "_inputs", None)))
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
    """Review the local app map and promote docs facts into the built-in one (05 Architecture, two layers)."""
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


def _later(phase: int):
    def run(args) -> int:
        print(f"`{args.cmd}` arrives in phase {phase} (see 05 Architecture, Build phases).", file=sys.stderr)
        return 2
    return run


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
    pl.add_argument("tutorial")
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

    for name, phase in (("compile", 5), ("eval", 5)):
        p = sub.add_parser(name, help=f"phase {phase}")
        p.add_argument("rest", nargs="*")
        p.set_defaults(func=_later(phase))

    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")   # ✓ » on a cp1252 console
        except (AttributeError, ValueError):
            pass
    from engine.dpi import make_dpi_aware
    make_dpi_aware()
    return args.func(args)
