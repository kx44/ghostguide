"""Local WebSocket between the engine and the overlay (live step 7). JSON text frames, one message each.

    python -m engine play tutorials/youtube-clone-vscode.md          # then start the overlay
    python -m engine play … --record cache/logs/play.jsonl           # also log every message sent

Only binds 127.0.0.1. REST /compile arrives with the compiler (phase 5).
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Optional

from engine.live.player import Player
from engine.schema import messages as m

DEFAULT_PORT = 8765
CAPTURE_SETTLE_S = 0.08    # overlay clears, compositor shows the app, then we grab the ring


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
                log=print) -> None:
    from websockets.asyncio.server import serve as ws_serve

    clients: set = set()
    rec = Recorder(record)
    loop = asyncio.get_running_loop()

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

    async def handler(ws):
        clients.add(ws)
        log(f"overlay connected ({len(clients)} client{'s' if len(clients) > 1 else ''})")
        try:
            async for raw in ws:
                try:
                    kind = json.loads(raw).get("type", "?")
                except ValueError:
                    kind = "?"
                out = await asyncio.to_thread(player.handle, raw)
                s = player.session
                where = "finished" if s.finished else f"step {s.current}/{s.of}" + (" (hidden)" if s.hidden else "")
                log(f"  ← {kind:8s} → {where}")
                await send_all(out)
        finally:
            clients.discard(ws)
            log("overlay disconnected")

    async with ws_serve(handler, "127.0.0.1", port, max_size=2 ** 20):
        log(f"engine listening on ws://127.0.0.1:{port} · {player.session.tutorial.meta.title}")
        try:
            await asyncio.Future()
        finally:
            rec.close()
