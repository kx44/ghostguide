"""What the code review found, each with the case that showed it."""
import json
import sys

import pytest

from engine.basefile.parse import parse_file
from engine.compile.adapters import SourceError
from engine.compile.adapters import video
from engine.compile.passes.extract import extract_segment
from engine.compile.timeline import Evidence, Segment
from engine.live import execute
from engine.live.player import Player
from engine.live.session import Session
from engine.models.client import BudgetExceeded, ModelClient
from engine.schema.messages import Box
from engine.schema.tutorial import Source, Step, Target

HELLO = {"type": "hello", "displays": [{"id": 0, "x": 0, "y": 0, "w": 2000, "h": 1000, "primary": True}]}
BOX = Box(x=100, y=100, w=20, h=20)


class FakeLocator:
    last_how = ""
    last_stage = "uia"
    last_extra = None
    box = None

    def locate(self, step):
        return self.box, None


def test_a_step_takes_its_colours_from_the_app_once_its_target_is_found():
    """It used to remember the Windows theme it fell back on before the box came, so a light app got dark-scheme colours."""
    loc = FakeLocator()
    p = Player(Session(parse_file("tutorials/mug-solidworks.md")), locator=loc,
               scheme_fn=lambda box: ("light", 0.8) if box else ("dark", None))
    p.handle(HELLO)
    assert p.last_guide.scheme == "dark"            # nothing measured yet: the Windows theme
    loc.box = BOX
    p.apply_located(p.locate_current())
    assert p.last_guide.scheme == "light"           # the app decides
    p.handle({"type": "next"})
    assert p.last_guide.scheme == "light"           # the next step keeps those colours while it looks, no flip to the theme


def test_scheme_is_measured_once_per_step():
    calls = []

    def fn(box):
        calls.append(box)
        return "light", 0.8
    loc = FakeLocator()
    loc.box = BOX
    p = Player(Session(parse_file("tutorials/mug-solidworks.md")), locator=loc, scheme_fn=fn)
    p.handle(HELLO)
    p.apply_located(p.locate_current())
    p.apply_located(p.locate_current())
    assert sum(1 for b in calls if b is not None) == 1


@pytest.mark.skipif(sys.platform != "win32", reason="input is Windows")
def test_the_cursor_comes_back_even_when_it_refuses(monkeypatch):
    spots = []
    monkeypatch.setattr(execute, "_cursor", lambda: (11, 22))

    class U32:
        @staticmethod
        def SetCursorPos(x, y):
            spots.append((x, y))
    import ctypes
    monkeypatch.setattr(ctypes.windll, "user32", U32, raising=False)
    ex = execute.Executor("app")

    def refuse(ops):
        spots.append("moved to test")
        return "Something is covering that spot"
    monkeypatch.setattr(ex, "refuse", refuse)
    assert "covering" in ex.run([execute.Op("click", at=(500, 500))])
    assert spots[-1] == (11, 22)


def _step(**params):
    return Step(n=1, title="T", action="shortcut", target=Target(label="x", kind="button"), params=params, check="c",
                source=Source(t="00:01"), confidence="high")


def test_keys_written_as_a_word_arent_pressed_letter_by_letter():
    assert not execute.can_do(_step(keys="Esc"), None)
    assert execute.can_do(_step(keys=["Esc"]), None)


def test_a_saved_position_that_isnt_a_number_is_ignored(tmp_path):
    p = tmp_path / "s.json"
    tut = parse_file("tutorials/mug-solidworks.md")
    p.write_text(json.dumps({"tutorial": tut.meta.title, "of": len(tut.steps), "current": "x", "statuses": ["pending"] * len(tut.steps)}), encoding="utf-8")
    s = Session(tut, save_path=p)
    assert s.restore() is False and s.current == 1


def test_two_clients_see_each_others_reservations(tmp_path):
    from engine.models.client import text_part

    log = tmp_path / "cost.jsonl"
    a = ModelClient(mode="live", budget_usd=0.02, cost_log=log, cassette_dir=tmp_path / "c")
    b = ModelClient(mode="live", budget_usd=0.02, cost_log=log, cassette_dir=tmp_path / "c")
    a._reserve(0.015)
    with pytest.raises(BudgetExceeded):
        b._reserve(0.015)
    a._release(0.015)
    b._reserve(0.015)
    b._release(0.015)


def test_a_typed_time_that_isnt_one_says_so():
    with pytest.raises(SourceError, match="isn't a time"):
        video.seconds("ten past")
    assert video.seconds("01:28") == 88


def test_two_local_videos_with_one_name_arent_one_tutorial(tmp_path, monkeypatch):
    monkeypatch.setattr(video, "keyframe_times", lambda frames, n: [])
    monkeypatch.setattr(video, "_grey_frames", lambda v: [])
    a, b = tmp_path / "a" / "lesson.mp4", tmp_path / "b" / "lesson.mp4"
    a.parent.mkdir()
    b.parent.mkdir()
    a.write_bytes(b"x" * 10)
    b.write_bytes(b"x" * 20)
    ha = video.from_video(a, client=None, turns=[]).hash
    hb = video.from_video(b, client=None, turns=[]).hash
    assert ha != hb


def test_a_reply_that_isnt_an_object_counts_as_unreadable():
    from engine.compile.passes import CompileError
    from engine.models.client import Reply

    class C:
        def chat(self, **kw):
            return Reply(text="[1, 2]")
    with pytest.raises(CompileError, match="unreadable"):
        extract_segment(C(), "m", Evidence("text", "h", []), Segment(n=1, items=[]))
