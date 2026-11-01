"""Local WebSocket between the engine and the overlay (live step 7). JSON text frames, one message each.

    python -m engine play tutorials/youtube-clone-vscode.md          # then start the overlay
    python -m engine play … --record cache/logs/play.jsonl           # also log every message sent

    python -m engine play                                            # nothing loaded yet: import one from the overlay

Only binds 127.0.0.1, and refuses browsers. Importing a tutorial (compile_* messages) runs in the background, so the current one keeps playing.
"""
from __future__ import annotations

import asyncio
import json
import time
import traceback
from pathlib import Path
from typing import Callable, Optional

from engine.live.player import Player
from engine.schema import messages as m

DEFAULT_PORT = 8765
CAPTURE_SETTLE_S = 0.08    # overlay clears, compositor shows the app, then we grab the ring
POLL_S = 1.0               # how often a live locator re-finds the current step's target and checks it
CLICK_SETTLE_S = 0.25      # after a click, let the app react before checking
TYPE_WAKE_S = 1.3          # after the last key, check once typing has paused (verify.TYPE_SETTLE_S + a bit)


class Recorder:
    """Writes every message sent to the overlay as JSON lines {t: ms since start, msg}, the format
    the overlay's `--replay` plays back."""

    def __init__(self, path: Optional[Path]):
        self.path = path
        self.t0 = time.monotonic()
        self._f = None
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._f = path.open("w", encoding="utf-8")

    def write(self, msg: m._Msg, t_ms: Optional[int] = None) -> None:
        if not self._f:
            return
        t = int((time.monotonic() - self.t0) * 1000) if t_ms is None else t_ms
        self._f.write(json.dumps({"t": t, "msg": msg.to_wire()}, ensure_ascii=False) + "\n")
        self._f.flush()

    def close(self) -> None:
        if self._f:
            self._f.close()


async def serve(player: Optional[Player], port: int = DEFAULT_PORT, record: Optional[Path] = None,
                log=print, inputs=None, importer: Optional[Callable] = None, opener: Optional[Callable] = None,
                on_end: Optional[Callable[[], None]] = None) -> None:
    """`inputs`: a live/inputs.Recent fed by the input watcher; a click or a pause after typing wakes the
    step check at once instead of at the next tick. `player` may be None until a tutorial is opened.
    `importer(msg, progress)` compiles and returns a CompileDone; `opener(path)` returns (Player, inputs)."""
    from websockets.asyncio.server import serve as ws_serve

    clients: set = set()
    rec = Recorder(record)
    loop = asyncio.get_running_loop()
    busy = asyncio.Lock()      # one player call at a time; the slow locator walk itself runs outside it
    poke_locate, poke_check = asyncio.Event(), asyncio.Event()
    ended = loop.create_future()

    class poke:                # set after each overlay message: locate and check the (new) step now, not in a second
        @staticmethod
        def set() -> None:
            poke_locate.set()
            poke_check.set()

    async def send_all(msgs: list[m._Msg]) -> None:
        for msg in msgs:
            rec.write(msg)
            data = m.dumps(msg)
            for ws in list(clients):
                try:
                    await ws.send(data)
                except Exception:      # a client that went away mid-send is dropped below
                    clients.discard(ws)

    def before_capture() -> None:
        # Runs in the worker thread: clear the overlay so our own outline isn't measured.
        asyncio.run_coroutine_threadsafe(send_all([m.Clear(reason="capture")]), loop).result(timeout=2)
        time.sleep(CAPTURE_SETTLE_S)

    if player is not None:
        player.before_capture = before_capture

    key_timer = None

    def wake_in(delay: float) -> None:
        loop.call_later(delay, poke.set)

    def on_input(ev) -> None:          # input watcher thread
        nonlocal key_timer
        if ev.kind == "down":
            loop.call_soon_threadsafe(wake_in, CLICK_SETTLE_S)
        elif ev.kind == "key":
            def rearm():
                nonlocal key_timer
                if key_timer is not None:
                    key_timer.cancel()
                key_timer = loop.call_later(TYPE_WAKE_S, poke.set)    # once typing pauses
            loop.call_soon_threadsafe(rearm)

    if inputs is not None:
        inputs.listeners.append(on_input)
        inputs.pause(True)         # until an overlay connects

    compiling = False

    async def start_import(data: dict) -> None:
        nonlocal compiling
        if importer is None or compiling:
            await send_all([m.CompileDone(ok=False, error="A compile is already running." if compiling else "This engine can't compile.")])
            return
        compiling = True

        def progress(stage: str, pct: float) -> None:      # compile worker thread
            asyncio.run_coroutine_threadsafe(send_all([m.CompileProgress(stage=stage, pct=pct)]), loop)

        async def run() -> None:
            nonlocal compiling
            try:
                done = await asyncio.to_thread(importer, m.Import.model_validate(data), progress)
            except Exception as e:
                log("  compile failed:\n" + traceback.format_exc())
                done = m.CompileDone(ok=False, error=f"Something went wrong: {e}")
            compiling = False
            log(f"  compile: {'done ' + str(done.path) if done.ok else done.error}")
            await send_all([done])

        asyncio.create_task(run())

    async def open_tutorial(path: str) -> None:
        nonlocal player, inputs
        if opener is None:
            return
        async with busy:
            try:
                new, new_inputs = await asyncio.to_thread(opener, path)
            except Exception as e:
                log("  open failed:\n" + traceback.format_exc())
                await send_all([m.Toast(text=f"Couldn't open that tutorial: {e}", kind="warn", ms=6000)])
                return
            new.before_capture = before_capture
            player = new
            if new_inputs is not None and new_inputs is not inputs:
                inputs = new_inputs
                inputs.listeners.append(on_input)
                inputs.pause(not clients)
            out = await asyncio.to_thread(player.handle, json.dumps({"type": "hello", "displays": last_displays}))
        await send_all(out)
        poke.set()

    last_displays: list = []

    async def fetch_source(p: Player) -> None:
        """A page the source view doesn't hold: slow, so the buttons keep working meanwhile."""
        url, p.sources.to_fetch = p.sources.to_fetch, None
        await asyncio.to_thread(p.sources.fetch, url)
        if p is player:
            await send_all(p.source_fetched())

    async def handler(ws):
        clients.add(ws)
        if inputs is not None:
            inputs.pause(False)
        log(f"overlay connected ({len(clients)} client{'s' if len(clients) > 1 else ''})")
        try:
            async for raw in ws:
                try:
                    data = json.loads(raw)
                    kind = data.get("type", "?")
                except (ValueError, AttributeError):     # not JSON, or JSON that isn't an object
                    data, kind = {}, "?"
                if kind == "hello":
                    last_displays[:] = data.get("displays") or []
                if kind == "end":        # the overlay is quitting: the next run mustn't find this engine on the port
                    if not ended.done():
                        ended.set_result(None)
                    return
                if kind == "import":
                    await start_import(data)
                    continue
                if kind == "open_tutorial":
                    await open_tutorial(str(data.get("path")))
                    continue
                if player is None:
                    continue
                async with busy:
                    try:
                        out = await asyncio.to_thread(player.handle, raw)
                    except Exception as e:     # one bad message mustn't cut the overlay off
                        log(f"  {kind} failed:\n" + traceback.format_exc())
                        out = [m.Toast(text=f"That didn't work: {type(e).__name__}", kind="warn", ms=4000)]
                s = player.session
                where = "finished" if s.finished else f"step {s.current}/{s.of}" + (" (hidden)" if s.hidden else "")
                log(f"  ← {kind:8s} → {where}")
                await send_all(out)
                if kind in ("source", "source_file"):
                    if player.sources.to_fetch:
                        asyncio.create_task(fetch_source(player))
                    continue         # nothing about the step changed
                poke.set()
        finally:
            clients.discard(ws)
            if inputs is not None and not clients:
                inputs.pause(True)
            log("overlay disconnected")

    async def round_loop(event: asyncio.Event, one_round) -> None:
        last_error = None
        while True:
            try:
                await asyncio.wait_for(event.wait(), POLL_S)
            except asyncio.TimeoutError:
                pass
            event.clear()
            if not clients or player is None:
                continue
            try:
                await one_round()
            except Exception as e:     # one bad round must never switch off the locator and the checks for good
                err = f"{type(e).__name__}: {e}"
                if err != last_error:
                    log("  round failed, carrying on:\n" + traceback.format_exc())
                    last_error = err

    last_how = None

    async def locate_round() -> None:
        nonlocal last_how
        p = player                                                   # a slow round mustn't land on a tutorial opened since
        if p.locator is None:
            return
        t0 = time.monotonic()
        if p.start_open:
            async with busy:
                out = await asyncio.to_thread(p.start_round)
            await send_all(out)
        found = await asyncio.to_thread(p.locate_current)           # slow; buttons keep working meanwhile
        if p is not player:
            return
        async with busy:
            out = await asyncio.to_thread(p.apply_located, found)
        how = getattr(p.locator, "last_how", None)
        if how != last_how:
            log(f"  locate step {found[0] if found else '-'}: {how} ({time.monotonic() - t0:.1f}s)")
            last_how = how
        await send_all(out)

    last_check = None

    async def check_round() -> None:
        nonlocal last_check
        p = player
        if p.tracker is None:
            return
        checked = await asyncio.to_thread(p.check_round)            # rule checks reuse the locator's dump
        if p is not player:
            return
        was = p.session.current
        async with busy:
            # In a thread, like every other player call: drawing a step can measure its colours, which clears the overlay
            # through this very loop, so on the loop itself that waits two seconds for nothing and then fails.
            out = await asyncio.to_thread(p.apply_checked, checked)
        v = p.tracker.cache.get(checked[0]) if checked else None
        said = (checked[0], v.result, v.why) if v else None
        if said != last_check:
            log(f"  check step {said[0]}: {said[1]} ({said[2]})" if said else "  check: -")
            last_check = said
        s = p.session
        if s.finished or s.current != was:
            log(f"  ✓ auto → {'finished' if s.finished else f'step {s.current}/{s.of}'}")
        await send_all(out)

    # Only the overlay: browsers put an Origin on every WebSocket and don't apply their same-origin rule to them, so
    # without `origins` any web page open on this PC could connect and press Do it for me or start a paid compile.
    async with ws_serve(handler, "127.0.0.1", port, max_size=2 ** 20, origins=[None]):
        log(f"engine listening on ws://127.0.0.1:{port} · {player.session.tutorial.meta.title if player else 'no tutorial yet: import one'}")
        # Apart, so a slow model call in one never holds up the other: the check must see a dialog open the moment
        # it opens, even while Spark is still looking for the next step's button.
        tasks = [asyncio.create_task(round_loop(poke_locate, locate_round)),
                 asyncio.create_task(round_loop(poke_check, check_round))]
        try:
            await ended
            if on_end is not None:        # a read of a window can be mid-way, and must not keep the port or the process
                on_end()
        finally:
            for t in tasks:
                t.cancel()
            rec.close()
