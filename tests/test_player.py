import asyncio
import json

import pytest

from engine import config
from engine.basefile.parse import parse_file
from engine.live.locate.pinned import Pins
from engine.live.player import Player
from engine.live.session import Session

HELLO = {"type": "hello", "displays": [{"id": 0, "x": 0, "y": 0, "w": 1920, "h": 1080, "primary": True}]}


def player(scheme_fn=None, override="dark"):
    s = Session(parse_file(config.TUTORIALS / "youtube-clone-vscode.md"))
    return Player(s, Pins.load("tests/fixtures/pins/youtube-clone-vscode.yaml"), scheme_fn=scheme_fn,
                  scheme_override=override)


def types(msgs):
    return [x.type for x in msgs]


def test_hello_sends_state_then_guide():
    p = player()
    out = p.handle(HELLO)
    assert types(out) == ["state", "guide"]
    assert out[1].style == "outline" and out[1].box.x == 214 and out[1].scheme == "dark"


def test_next_marks_ok_and_moves():
    p = player()
    p.handle(HELLO)
    out = p.handle({"type": "next"})
    assert types(out) == ["mark", "state", "guide"] and out[2].step.n == 2


def test_skip_hide_resume_jump_and_finish():
    p = player()
    p.handle(HELLO)
    out = p.handle({"type": "skip"})
    assert types(out) == ["state", "guide", "toast"] and out[0].statuses[0] == "skipped"
    out = p.handle({"type": "hide"})
    assert types(out) == ["state", "clear"] and out[0].hidden
    assert p.handle({"type": "hide"}) == []
    assert types(p.handle({"type": "resume"})) == ["state", "guide"]
    out = p.handle({"type": "jump", "n": 23})
    assert out[1].style == "keycaps"
    out = p.handle({"type": "next"})
    assert out[0].finished and out[1].type == "clear" and "complete" in out[-1].text
    assert types(p.handle({"type": "jump", "n": 99})) == ["toast"]


def test_show_me_and_unbuilt_features():
    p = player()
    p.handle(HELLO)
    sm = p.handle({"type": "show_me"})[0]
    assert sm.type == "show_me" and sm.to == (225, 95)
    assert "phase 4" in p.handle({"type": "do_it"})[0].text
    assert p.handle("garbage")[0].kind == "warn"


def test_scheme_measured_once_per_box():
    calls = []

    def fn(box):
        calls.append(box)
        return ("light", 0.9)

    p = player(scheme_fn=fn, override=None)
    p.handle(HELLO)
    p.handle({"type": "back"})          # noop at step 1
    p.handle({"type": "next"}); p.handle({"type": "back"})
    assert p.last_guide.scheme == "light" and len(calls) == 2      # step 1 box, step 2 box


def test_websocket_round_trip():
    websockets = pytest.importorskip("websockets")
    from websockets.asyncio.client import connect

    from engine.server import serve

    async def run():
        p = player()
        task = asyncio.create_task(serve(p, port=8799, log=lambda *_: None))
        for _ in range(50):
            try:
                ws = await connect("ws://127.0.0.1:8799")
                break
            except OSError:
                await asyncio.sleep(0.05)
        async with ws:
            await ws.send(json.dumps(HELLO))
            got = [json.loads(await ws.recv()) for _ in range(2)]
            await ws.send('{"type":"next"}')
            got += [json.loads(await ws.recv()) for _ in range(3)]
        task.cancel()
        return got

    got = asyncio.run(run())
    assert [g["type"] for g in got] == ["state", "guide", "mark", "state", "guide"]
    assert got[1]["box"] == {"x": 214, "y": 84, "w": 22, "h": 22} and got[4]["step"]["n"] == 2


def test_walk_writes_replay(tmp_path):
    from engine.cli import main

    out = tmp_path / "walk.jsonl"
    assert main(["play", "tutorials/youtube-clone-vscode.md", "--pins", "tests/fixtures/pins/youtube-clone-vscode.yaml",
                 "--scheme", "dark", "--restart", "--walk", str(out), "--every", "1000"]) == 0
    lines = [json.loads(l) for l in out.read_text().splitlines()]
    assert lines[0]["t"] == 0 and lines[0]["msg"]["type"] == "state"
    guides = [l["msg"] for l in lines if l["msg"]["type"] == "guide"]
    assert [g["step"]["n"] for g in guides] == list(range(1, 24))
    assert lines[-1]["msg"]["type"] == "toast" and all(a["t"] <= b["t"] for a, b in zip(lines, lines[1:]))


def test_pin_as_you_go(tmp_path):
    s = Session(parse_file(config.TUTORIALS / "youtube-clone-vscode.md"))
    path = tmp_path / "pins.yaml"
    p = Player(s, Pins(), scheme_override="dark", pins_path=path)
    out = p.handle(HELLO)
    assert out[1].style == "card" and "Ctrl+Alt+P" in out[1].card.dev_hint
    out = p.handle({"type": "pin", "at": [300, 90]})
    assert "bottom-right" in out[1].card.dev_hint and "Top-left saved" in out[-1].text
    out = p.handle({"type": "pin", "at": [276, 112]})          # corners in any order
    assert out[1].style == "outline" and out[1].box.model_dump() == {"x": 276, "y": 90, "w": 24, "h": 22}
    assert out[1].card.dev_hint is None and Pins.load(path).box(1).x == 276
    p.handle({"type": "jump", "n": 6})
    assert p.last_guide.card.dev_hint is None                 # shortcut: no pin needed
    p.handle({"type": "jump", "n": 1})
    out = p.handle({"type": "unpin"})
    assert out[1].style == "card" and Pins.load(path).box(1) is None
    p.handle({"type": "pin", "at": [5, 5]})
    assert "Too small" in p.handle({"type": "pin", "at": [6, 6]})[-1].text
