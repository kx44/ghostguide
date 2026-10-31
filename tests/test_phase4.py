"""Phase 4, the pure parts: vision memory and regions, route hops, Wonder, Do it for me, the start check, the model gate."""
from types import SimpleNamespace

from PIL import Image

from engine.basefile.parse import parse_file
from engine.live import execute, startcheck
from engine.live.locate.menu import Hops, Wonder, hop_label
from engine.live.locate.resolver import Resolver
from engine.live.locate.solidworks import tree_item
from engine.live.locate.vision import SparkVision, region_box, region_for
from engine.live.plan import Planner
from engine.live.player import Player
from engine.live.session import Session
from engine.live.verify import Ladder, Tracker, Verdict
from engine.live.windows import document_open, foreign_browser
from engine.models.tools import MenuPath, NotFound, PointAt
from engine.schema.messages import Box

MUG = parse_file("tutorials/mug-solidworks.md")


class FakeClient:
    def __init__(self, *calls):
        self.calls = list(calls)
        self.n = 0

    def chat(self, **kw):
        self.n += 1
        self.kw = kw
        return SimpleNamespace(tool_calls=[self.calls[min(self.n - 1, len(self.calls) - 1)]])


def clock_at(t):
    return lambda: t[0]


def blank(colour=255, size=(800, 400)):
    return Image.new("RGB", size, (colour, colour, colour))


def vision(client, img, t):
    return SparkVision("SOLIDWORKS", client=client, grab=lambda: (img[0], (0, 0), 1.0), clock=clock_at(t))


# ---------- vision ----------
def test_vision_answer_stands_while_its_pixels_do():
    img, t = [blank()], [100.0]
    c = FakeClient(PointAt(x=100, y=50, w=40, h=20, confidence="high"), PointAt(x=100, y=50, w=40, h=20, confidence="high"))
    v = vision(c, img, t)
    first = v.find(MUG.step(10))
    assert first is not None and c.n == 2                  # first look + the zoomed one
    t[0] += 60
    assert v.find(MUG.step(10)) == first and c.n == 2      # asked again every second, paid once


def test_vision_miss_stands_until_the_window_changes_and_calls_are_capped():
    img, t = [blank()], [100.0]
    c = FakeClient(NotFound(reason="no"))
    v = vision(c, img, t)
    assert v.find(MUG.step(10)) is None and c.n == 1
    t[0] += 60
    assert v.find(MUG.step(10)) is None and c.n == 1       # same window: same miss
    for colour in (0, 128, 40, 200, 90):
        img[0] = blank(colour)
        t[0] += 60
        v.find(MUG.step(10))
    assert c.n == 3                                        # MAX_CALLS, however much the window changes
    v.forget(10)
    img[0] = blank(10)
    t[0] += 60
    v.find(MUG.step(10))
    assert c.n == 4                                        # the step showing again gets a fresh allowance


def test_vision_refuses_a_box_too_big_to_be_a_control():
    img, t = [blank()], [100.0]
    v = vision(FakeClient(PointAt(x=400, y=200, w=700, h=380, confidence="high")), img, t)
    assert v.find(MUG.step(10)) is None


def test_regions_follow_where():
    assert region_for(MUG.step(10)) == "ribbon"            # Sketch tab, CommandManager
    assert region_for(MUG.step(11)) == "panel"             # Offset Entities PropertyManager
    assert region_for(MUG.step(15)) == "corner"            # confirmation corner
    assert region_for(MUG.step(6)) == "window"             # the canvas
    assert region_box("ribbon", 2560, 1528, 1.5) == (0, 0, 2560, 188)
    x, y, w, h = region_box("panel", 2560, 1528, 1.5)
    assert (x, y, w) == (0, 128, 450) and y + h == 1528


# ---------- routes ----------
def test_hops_tick_on_a_click_in_the_chip_and_fall_back_when_the_menu_closed():
    hit = [False]
    h = Hops(clicked=lambda box, since: hit[0], clock=lambda: 1.0)
    path = ["Sketch", "Line ▾", "Centerline"]
    assert h.current(5, path) == 0
    h.found(5, Box(x=1, y=1, w=9, h=9))
    assert h.current(5, path) == 0
    hit[0] = True
    assert h.current(5, path) == 1
    hit[0] = False
    h.found(5, Box(x=2, y=2, w=9, h=9))
    assert h.current(5, path) == 1
    h.back_to_start(5)
    assert h.current(5, path) == 0
    assert hop_label("Line ▾") == "Line"


class Stage:
    follows_hops = True
    window = "SOLIDWORKS"
    last_how = "not found"
    last_extra = {}

    def locate(self, step, label=None):
        return None, None


class VisionStub:
    last_how, last_line, last_conf = "vision: no", None, ""

    def __init__(self, route=None, box=None):
        self.last_route, self.box = route, box

    def find(self, step, label=None):
        return self.box


def test_wonder_asked_once_only_when_no_route_is_known_and_its_route_goes_to_the_local_map():
    calls = []

    class Store:
        def get(self, label): return None
        def names(self, label): return [label]
        def add_facts(self, label, **facts): calls.append((label, facts))

    c = FakeClient(MenuPath(path=["Tools", "Sketch Tools", "Offset Entities"], confidence="high"))
    w = Wonder("SOLIDWORKS", client=c, grab=lambda: (blank(), (0, 0), 1.0), store=Store())
    r = Resolver(Stage(), Store(), vision=VisionStub(), wonder=w)
    assert r.locate(MUG.step(10)) == (None, None)
    assert r.last_stage == "wonder" and r.last_extra["route"]["path"][0] == "Tools"
    r.locate(MUG.step(10))
    assert c.n == 1 and calls == [("Offset Entities", {"menu_path": ["Tools", "Sketch Tools", "Offset Entities"],
                                                        "source": "Muse Wonder, unreviewed"})]
    c2 = FakeClient(NotFound(reason="no"))
    w2 = Wonder("SOLIDWORKS", client=c2, grab=lambda: (blank(), (0, 0), 1.0))
    r2 = Resolver(Stage(), None, vision=VisionStub(), wonder=w2)
    r2.locate(MUG.step(16))                               # Revolve has a menu path: no need for Wonder
    assert c2.n == 0 and r2.last_stage == "route"
    r2.locate(MUG.step(6))                                # the canvas is never Wonder's
    assert c2.n == 0


def test_spark_route_used_only_when_sure_and_first_hop_outlined():
    sure = {"path": ["Sketch", "Offset Entities"], "confidence": "high", "by": "spark"}
    r = Resolver(Stage(), None, vision=VisionStub(route=sure))
    assert r.locate(MUG.step(10))[0] is None and r.last_stage == "route"
    unsure = {"path": ["Sketch", "Offset Entities"], "confidence": "low", "by": "spark"}
    r = Resolver(Stage(), None, vision=VisionStub(route=unsure))
    r.locate(MUG.step(10))
    assert "route" not in r.last_extra


# ---------- SolidWorks UIA ----------
def test_tree_item_takes_the_visible_row():
    els = [{"type": "TreeItem", "name": "Front Plane", "rect": [0, 0, 0, 0]},
           {"type": "Text", "name": "Front Plane", "rect": [1, 1, 9, 9]},
           {"type": "TreeItem", "name": "Front Plane", "rect": [5, 6, 90, 30]}]
    assert tree_item(els, "front plane")["rect"] == [5, 6, 90, 30]
    assert tree_item(els, "Top Plane") is None


def test_a_browser_tab_about_the_app_is_not_the_app():
    assert foreign_browser("10 steps in SOLIDWORKS - Google Chrome", "SOLIDWORKS")
    assert not foreign_browser("Document - Google Chrome", "Google Chrome")
    assert not foreign_browser("SOLIDWORKS 2026 - [Part1]", "SOLIDWORKS")
    assert document_open("SOLIDWORKS Design Standard 2026 SP4.1 - Academic Use Only - [Part1 *]")
    assert not document_open("SOLIDWORKS Design Standard 2026 SP4.1 - Academic Use Only")


# ---------- Do it for me ----------
BOX = Box(x=100, y=200, w=40, h=20)


def test_do_it_never_draws_on_the_canvas():
    assert not execute.can_do(MUG.step(6), BOX)            # draw_line on the canvas
    assert not execute.can_do(MUG.step(28), BOX)           # pick in the model
    assert execute.can_do(MUG.step(10), BOX) and not execute.can_do(MUG.step(10), None)
    assert execute.can_do(MUG.step(20), None)              # a shortcut needs no box
    assert execute.can_do(MUG.step(4), None)               # …nor a route with a shortcut


def test_do_it_ops():
    assert [o.kind for o in execute.plan(MUG.step(11), BOX)] == ["click", "keys", "text", "keys"]
    assert execute.plan(MUG.step(11), BOX)[2].text == "2"
    assert execute.plan(MUG.step(11), BOX)[3].keys == ("Tab",)
    assert execute.plan(MUG.step(30), BOX)[1].keys == ("F2",)
    assert execute.plan(MUG.step(30), BOX)[3].keys == ("Enter",)
    assert execute.plan(MUG.step(2), BOX)[0].count == 2
    assert execute.plan(MUG.step(20), None)[0].keys == ("Ctrl", "1")
    assert execute.plan(MUG.step(4), None)[0].keys == ("Ctrl", "1")


def test_found_by_sight_waits_for_a_second_press():
    assert execute.needs_confirm(MUG.step(10), "vision")
    assert execute.needs_confirm(MUG.step(10), "appmap")
    assert not execute.needs_confirm(MUG.step(10), "uia")
    assert not execute.needs_confirm(MUG.step(20), "vision")


class FakeExecutor:
    def __init__(self, refuse=None):
        self.ran, self.refusal = [], refuse

    def run(self, ops):
        self.ran.append(ops)
        return self.refusal


def player_at(n, stage="vision", executor=None, box=BOX):
    s = Session(MUG)
    s.current = n
    p = Player(s, scheme_override="light", executor=executor or FakeExecutor(),
               locator=SimpleNamespace(last_how="", last_stage=stage, last_extra={}, locate=lambda st: (box, None)))
    p.handle({"type": "hello", "displays": [{"id": 0, "x": 0, "y": 0, "w": 2560, "h": 1600}]})
    p.refresh()
    return p


def test_card_offers_do_it_only_when_it_can():
    assert "do_it" in player_at(10).last_guide.card.actions
    assert "do_it" not in player_at(6).last_guide.card.actions
    assert "do_it" not in player_at(10, box=None).last_guide.card.actions
    s = Session(MUG)
    s.current = 10
    assert "do_it" not in Player(s, scheme_override="light").current()[1].card.actions


def test_second_press_runs_and_a_refusal_is_said():
    ex = FakeExecutor()
    p = player_at(10, executor=ex)
    assert "Check the outline" in p.handle({"type": "do_it"})[0].text and ex.ran == []
    assert p.handle({"type": "do_it"})[0].text.startswith("Done for you") and len(ex.ran) == 1
    ex = FakeExecutor(refuse="Bring SOLIDWORKS to the front first")
    p = player_at(10, stage="uia", executor=ex)
    assert p.handle({"type": "do_it"})[0].kind == "warn"
    p = player_at(10, executor=FakeExecutor())
    p.handle({"type": "do_it"})
    p.handle({"type": "next"})
    p.handle({"type": "back"})                             # arming doesn't survive moving away
    assert "Check the outline" in p.handle({"type": "do_it"})[0].text


# ---------- suggested values ----------
def test_suggested_value_goes_in_the_card_labelled():
    g = Planner(MUG).plan(MUG.step(11), BOX)
    assert g.style == "code_card" and g.extra["value"] == "2"
    assert g.card.suggested.startswith("2 mm, side inside")
    assert g.card.detail == "Type 2 in Offset Distance."
    g = Planner(MUG).plan(MUG.step(43), BOX)
    assert g.card.detail == "Type 1 in Radius, then OK (green check)."
    g = Planner(MUG).plan(MUG.step(9), None)
    assert g.card.suggested == "length 100mm, radius at base 40mm"


def test_mask_is_for_geometry():
    pl = Planner(MUG)
    assert pl.style(MUG.step(28)) == "mask" and pl.style(MUG.step(42)) == "mask"
    assert pl.style(MUG.step(37)) == "outline"             # Sketch3 is a row in the tree
    g = pl.plan(MUG.step(28), Box(x=100, y=100, w=6, h=6))
    assert (g.box.w, g.box.h) == (44, 44) and g.box.x == 81


# ---------- start check ----------
SW = "SOLIDWORKS Design Standard 2026 SP4.1 - Academic Use Only"


def test_start_items():
    items = startcheck.evaluate(MUG.meta.start_state, "SOLIDWORKS", [SW], document_open)
    assert items == [{"text": "SOLIDWORKS open", "ok": True}, {"text": "no document", "ok": True}]
    assert not startcheck.holds_back(items)
    items = startcheck.evaluate(MUG.meta.start_state, "SOLIDWORKS", [SW + " - [Part1]"], document_open)
    assert items[1]["ok"] is False and startcheck.holds_back(items)
    assert startcheck.evaluate(MUG.meta.start_state, "SOLIDWORKS", [], document_open)[0]["ok"] is False
    assert startcheck.parts("A very long free-text state that goes on, " * 8) == []


def test_start_check_holds_step_one_until_ready_or_start_anyway():
    items = [[{"text": "no document", "ok": False}]]
    s = Session(MUG)
    p = Player(s, scheme_override="light", start_items=lambda: items[0])
    out = p.handle({"type": "hello"})
    assert [m.type for m in out] == ["state", "clear", "start_check"]
    assert p.locate_current() is None and p.check_round() is None   # nothing paid for meanwhile
    assert p.start_round() == []                                    # no change, no redraw
    items[0] = [{"text": "no document", "ok": True}]
    out = p.start_round()
    assert any(m.type == "guide" for m in out) and any(m.type == "toast" for m in out) and not p.start_open
    items[0] = [{"text": "no document", "ok": False}]
    p = Player(Session(MUG), scheme_override="light", start_items=lambda: items[0])
    p.handle({"type": "hello"})
    assert any(m.type == "guide" for m in p.handle({"type": "start_ok"}))
    resumed = Session(MUG)
    resumed.current = 5
    p = Player(resumed, scheme_override="light", start_items=lambda: items[0])
    assert not p.start_open


# ---------- the model gate ----------
def tracker(asked, idle=(9.0,), t=(100.0,)):
    img = [blank()]
    now = list(t)

    def model(step, png):
        asked.append(step.n)
        return Verdict("not_yet", "glimmer", why="no")
    tr = Tracker(MUG, "SOLIDWORKS", None, lambda w: [{"type": "Window", "name": "x"}], ladder=Ladder(glimmer=model),
                 idle_s=lambda: idle[0], grab=lambda step: img[0], clock=lambda: now[0])
    tr.current_n = 3
    return tr, img, now


def test_models_only_look_at_the_step_showing_when_you_pause_and_when_the_window_changed():
    asked = []
    idle = [9.0]
    tr, img, now = tracker(asked, idle)
    snap = tr.snapshot()
    assert tr.check(MUG.step(3), snap).why == "baseline taken"
    img[0] = blank(0)
    idle[0] = 0.2
    tr.check(MUG.step(3), snap)
    assert asked == []                                  # mid-action: wait
    idle[0] = 9.0
    tr.check(MUG.step(3), snap)
    assert asked == [3]
    img[0] = blank(128)
    now[0] += 1
    tr.check(MUG.step(3), snap)
    assert asked == [3]                                 # too soon
    now[0] += 60
    tr.check(MUG.step(3), snap)
    assert asked == [3, 3]
    now[0] += 60
    tr.check(MUG.step(3), snap)
    assert asked == [3, 3]                              # nothing new to look at
    tr.check(MUG.step(4), snap)                         # a later step, in the look-ahead
    assert asked == [3, 3]


def test_look_steps_and_hidden_never_reach_a_model():
    asked = []
    tr, img, now = tracker(asked)
    snap = tr.snapshot()
    tr.current_n = 40
    tr.check(MUG.step(40), snap)
    img[0] = blank(0)
    tr.check(MUG.step(40), snap)
    tr.current_n, tr.hidden = 3, True
    tr.check(MUG.step(3), snap)
    tr.check(MUG.step(3), snap)
    assert asked == []
