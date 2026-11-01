"""Finding the next steps' controls before they come up: from a picture only, ready when the step shows, and limited."""
import time
from types import SimpleNamespace

from PIL import Image

from engine.basefile.parse import parse_file
from engine.live.locate.boxcheck import BoxCheck
from engine.live.locate.menu import Hops
from engine.live.locate.resolver import Resolver, StepApps
from engine.live.locate.vision import AHEAD_MAX_ASKS, AHEAD_TRIES, SparkVision, _Memo, ahead_enabled
from engine.live.player import Player
from engine.live.session import Session
from engine.live.verify import Verdict
from engine.models.tools import NotFound, PointAt
from engine.schema.messages import Box

MUG = parse_file("tutorials/mug-solidworks.md")
NEW = MUG.step(1)


class Client:
    def __init__(self, *calls):
        self.calls, self.n = list(calls), 0

    def chat(self, **kw):
        self.n += 1
        return SimpleNamespace(tool_calls=[self.calls[min(self.n - 1, len(self.calls) - 1)]])


class NoUIA:
    last_how, last_extra, window = "not found", {}, "SOLIDWORKS"

    def locate(self, step, label=None):
        return None, None


def blank(colour=0):
    return Image.new("RGB", (400, 300), (colour, colour, colour))


def vision(client, screen):
    return SparkVision("SOLIDWORKS", client=client, grab=lambda: (screen[0], (0, 0), 1.0))


def wait_for(r):
    end = time.monotonic() + 5
    while r._ahead_running and time.monotonic() < end:
        time.sleep(0.01)
    assert not r._ahead_running


def here(v):
    return PointAt(x=50, y=50, w=20, h=20, confidence="high") if v else NotFound(reason="not there")


def test_a_box_found_ahead_is_ready_when_the_step_comes_up_with_no_new_call():
    c = Client(here(True))
    v = vision(c, [blank()])
    assert v.look_ahead(NEW) is not None
    asked = c.n
    v.forget(NEW.n)                    # what the player does as the step comes up
    assert v.find(NEW) is not None
    assert c.n == asked


def test_a_look_ahead_leaves_the_steps_own_allowance_whole():
    v = vision(Client(here(True)), [blank()])
    v.look_ahead(NEW)
    assert v.spent(NEW.n, NEW.target.label) is False and v._memo[(NEW.n, NEW.target.label)].calls == 0


def test_once_shown_a_step_gets_a_fresh_allowance_as_before():
    v = vision(Client(here(True)), [blank()])
    v.look_ahead(NEW)
    v.find(NEW)
    v.forget(NEW.n)
    assert (NEW.n, NEW.target.label) not in v._memo


def test_a_target_not_on_screen_waits_for_the_window_to_change_and_gets_few_tries():
    c = Client(here(False))
    screen = [blank()]
    v = vision(c, screen)
    assert v.look_ahead(NEW) is None and c.n == 1
    v.look_ahead(NEW)
    assert c.n == 1, "same window: no point paying again"
    for shade in (255, 0, 255):
        screen[0] = blank(shade)
        v.look_ahead(NEW)
    assert c.n == AHEAD_TRIES


def test_a_miss_ahead_doesnt_use_up_the_steps_own_looks():
    v = vision(Client(here(False)), [blank()])
    v.look_ahead(NEW)
    assert (NEW.n, NEW.target.label) not in v._memo


def test_looks_ahead_stop_at_a_limit_for_the_run():
    c = Client(here(False))
    v = vision(c, [blank()])
    v._ahead_asks = AHEAD_MAX_ASKS
    v.look_ahead(NEW)
    assert c.n == 0


def test_nothing_to_look_at_stays_on_this_pc():
    c = Client(here(True))
    v = SparkVision("SOLIDWORKS", client=c, grab=lambda: None)    # hidden, the tray switch, a secret in the title
    assert v.look_ahead(NEW) is None and c.n == 0


def test_the_step_waits_for_a_look_already_out_rather_than_paying_twice():
    c = Client(here(True))
    v = vision(c, [blank()])
    v._memo[(NEW.n, NEW.target.label)] = memo = _Memo(busy=True)
    assert v.find(NEW) is None and c.n == 0 and memo.shown and v.looking(NEW.n, NEW.target.label)


def finder(v, ahead=True, box_check=None):
    return Resolver(NoUIA(), None, None, v, None, Hops(), box_check=box_check, ahead=ahead)


def test_resolver_finds_ahead_in_the_background_only_when_on():
    c = Client(here(True))
    off = finder(vision(c, [blank()]), ahead=False)
    off.look_ahead([NEW])
    assert c.n == 0 and not off._ahead_running
    on = finder(vision(c, [blank()]))
    on.look_ahead([NEW])
    wait_for(on)
    assert c.n >= 1 and on.locate(NEW)[0] is not None


def test_the_resolver_shows_no_route_while_a_look_is_out():
    v = vision(Client(here(True)), [blank()])
    r = finder(v)
    v._memo[(NEW.n, NEW.target.label)] = _Memo(busy=True)
    assert r.locate(NEW) == (None, None)
    assert "already looking" in r.last_how and "route" not in r.last_extra and "search" not in r.last_extra


def test_only_controls_with_a_name_are_looked_for_ahead():
    c = Client(here(True))
    r = finder(vision(c, [blank()]))
    canvas = next(s for s in MUG.steps if s.target.kind == "canvas")
    r.look_ahead([canvas])
    assert c.n == 0 and not r._ahead_running


def test_the_second_opinion_is_waiting_too():
    said = []

    def stage(step, png, text, tag):
        said.append(tag)
        return Verdict("done")
    check = BoxCheck("SOLIDWORKS", [stage], lambda: (blank(), (0, 0), 1.0), start=lambda run: run())
    box = Box(x=40, y=40, w=20, h=20)
    check.say(NEW, "New", box, ahead=True)
    check.forget(NEW.n)
    assert check.say(NEW, "New", box) == ("yes", "") and len(said) == 1
    check.forget(NEW.n)                # once shown, a fresh look next time, as before
    assert not check._looks


def test_across_apps_only_the_app_in_front_is_looked_at():
    seen = []

    def make(name):
        return SimpleNamespace(window=name, look_ahead=lambda steps: seen.append((name, [s.n for s in steps])), forget=lambda n: None)
    main = make("Main")
    r = StepApps(main, "Main", make, in_front=lambda w: False, is_open=lambda w: None)
    r.look_ahead([NEW])
    assert seen == []
    r = StepApps(main, "Main", make, in_front=lambda w: w == "Main", is_open=lambda w: None)
    r.look_ahead([NEW])
    assert seen == [("Main", [NEW.n])]


def player(tmp_path, locator, inputs=None):
    s = Session(MUG, save_path=tmp_path / "s.json")
    p = Player(s, locator=locator, inputs=inputs, start_items=None)
    return p, s


def test_player_asks_for_the_next_steps_never_while_hidden(tmp_path):
    asked = []
    loc = SimpleNamespace(look_ahead=lambda steps: asked.append([x.n for x in steps]), locate=lambda step: (None, None), last_how="", last_extra={})
    p, s = player(tmp_path, loc)
    p.locate_current()
    assert asked == [[2, 3, 4]]
    p.start_open = True
    p.locate_current()
    assert asked[-1] == [1, 2, 3, 4]
    p.start_open = False
    s.hide()
    asked.clear()
    p.locate_current()
    assert asked == []


def test_next_after_clicking_the_outline_remembers_it(tmp_path):
    learned = []
    clicks = [SimpleNamespace(x=45, y=45, t=0.0)]
    inputs = SimpleNamespace(clicks=lambda within_s: clicks)
    loc = SimpleNamespace(learn=lambda step, box: learned.append(step.n) or True, locate=lambda step: (None, None), last_how="", last_extra={})
    p, s = player(tmp_path, loc, inputs)
    p._drawn[1] = [Box(x=40, y=40, w=20, h=20)]
    p.handle('{"type": "next"}')
    assert learned == [1]


def test_next_without_clicking_the_outline_remembers_nothing(tmp_path):
    learned = []
    inputs = SimpleNamespace(clicks=lambda within_s: [SimpleNamespace(x=300, y=300, t=0.0)])
    loc = SimpleNamespace(learn=lambda step, box: learned.append(step.n) or True, locate=lambda step: (None, None), last_how="", last_extra={})
    p, s = player(tmp_path, loc, inputs)
    p._drawn[1] = [Box(x=40, y=40, w=20, h=20)]
    p.handle('{"type": "next"}')
    assert learned == []


def test_it_follows_the_finding_switch(monkeypatch):
    from engine import config
    values = {"FINDER_VISION": "on", "FINDER_AHEAD": "off"}
    monkeypatch.setattr(config, "env", lambda k, d=None: values.get(k, d))
    assert not ahead_enabled()
    values["FINDER_AHEAD"] = "on"
    assert ahead_enabled()
    values["FINDER_VISION"] = "off"
    assert not ahead_enabled()
