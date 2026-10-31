"""Local WebSocket between the engine and the overlay (live step 7). JSON text frames, one message each.

    python -m engine play tutorials/youtube-clone-vscode.md          # then start the overlay
    python -m engine play … --record cache/logs/play.jsonl           # also log every message sent

Only binds 127.0.0.1. REST /compile arrives with the compiler (phase 5).
"""
from __future__ import annotations

import asyncio
import json
import time
import traceback
from pathlib import Path
from typing import Optional

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


async def serve(player: Player, port: int = DEFAULT_PORT, record: Optional[Path] = None,
                log=print, inputs=None) -> None:
    """`inputs`: a live/inputs.Recent fed by the input watcher; a click or a pause after typing wakes the
    step check at once instead of at the next tick."""
    from websockets.asyncio.server import serve as ws_serve

    clients: set = set()
    rec = Recorder(record)
    loop = asyncio.get_running_loop()
    busy = asyncio.Lock()      # one player call at a time; the slow locator walk itself runs outside it
    poke_locate, poke_check = asyncio.Event(), asyncio.Event()

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

    async def handler(ws):
        clients.add(ws)
        log(f"overlay connected ({len(clients)} client{'s' if len(clients) > 1 else ''})")
        try:
            async for raw in ws:
                try:
                    kind = json.loads(raw).get("type", "?")
                except ValueError:
                    kind = "?"
                async with busy:
                    out = await asyncio.to_thread(player.handle, raw)
                s = player.session
                where = "finished" if s.finished else f"step {s.current}/{s.of}" + (" (hidden)" if s.hidden else "")
                log(f"  ← {kind:8s} → {where}")
                await send_all(out)
                poke.set()
        finally:
            clients.discard(ws)
            log("overlay disconnected")

    async def round_loop(event: asyncio.Event, one_round) -> None:
        last_error = None
        while True:
            try:
                await asyncio.wait_for(event.wait(), POLL_S)
            except asyncio.TimeoutError:
                pass
            event.clear()
            if not clients:
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
        t0 = time.monotonic()
        if player.start_open:
            async with busy:
                out = await asyncio.to_thread(player.start_round)
            await send_all(out)
        found = await asyncio.to_thread(player.locate_current)      # slow; buttons keep working meanwhile
        async with busy:
            out = await asyncio.to_thread(player.apply_located, found)
        how = getattr(player.locator, "last_how", None)
        if how != last_how:
            log(f"  locate step {found[0] if found else '-'}: {how} ({time.monotonic() - t0:.1f}s)")
            last_how = how
        await send_all(out)

    last_check = None

    async def check_round() -> None:
        nonlocal last_check
        checked = await asyncio.to_thread(player.check_round)       # rule checks reuse the locator's dump
        async with busy:
            out = player.apply_checked(checked)
        v = player.tracker.cache.get(checked[0]) if checked else None
        said = (checked[0], v.result, v.why) if v else None
        if said != last_check:
            log(f"  check step {said[0]}: {said[1]} ({said[2]})" if said else "  check: -")
            last_check = said
        if out:
            s = player.session
            log(f"  ✓ auto → {'finished' if s.finished else f'step {s.current}/{s.of}'}")
        await send_all(out)

    async with ws_serve(handler, "127.0.0.1", port, max_size=2 ** 20):
        log(f"engine listening on ws://127.0.0.1:{port} · {player.session.tutorial.meta.title}")
        # Apart, so a slow model call in one never holds up the other: the check must see a dialog open the moment
        # it opens, even while Spark is still looking for the next step's button.
        tasks = []
        if player.locator is not None:
            tasks.append(asyncio.create_task(round_loop(poke_locate, locate_round)))
        if player.tracker is not None:
            tasks.append(asyncio.create_task(round_loop(poke_check, check_round)))
        try:
            await asyncio.Future()
        finally:
            for t in tasks:
                t.cancel()
            rec.close()
