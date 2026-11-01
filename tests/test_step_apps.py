"""A tutorial across programs (Step.app, StepApps), a model's look at a stuck rule check, and its look at a box found by sight."""
from PIL import Image

from engine.basefile.parse import parse_text
from engine.basefile.render import render_text as render
from engine.compile.passes.merge import to_tutorial
from engine.compile.timeline import Evidence
from engine.live.locate.boxcheck import MAX_LOOKS, WAIT_S, BoxCheck, picture
from engine.live.locate.resolver import Resolver, StepApps
from engine.live.player import Player
from engine.live.session import Session
from engine.live.verify import STUCK_S, Ladder, Tracker, Verdict
from engine.live.windows import Win, is_vscode, pick
from engine.schema.messages import Box
from engine.schema.tutorial import Source, SourceInfo, Step, Target, Tutorial, TutorialMeta, Verify


def step(n=1, app=None, action="click", label="Deploy", kind="button", verify=None, check="done"):
    return Step(n=n, title=f"Step {n}", app=app, action=action, target=Target(label=label, kind=kind), check=check,
                verify=verify, source=Source(anchor="#a"))


def tutorial(*steps):
    return Tutorial(meta=TutorialMeta(title="T", app="Visual Studio Code", source=SourceInfo(type="text")), steps=list(steps))


class Finder:
    last_how, last_stage, last_conf, last_seconds, last_t = "found", "uia", "", 0.0, 0.0
    last_extra: dict = {}
    last_els = [{"name": "main"}]
    vision = wonder = None

    def __init__(self, window):
        self.window = window
        self.asked = []
        self.forgot = []

    def locate(self, s):
        self.asked.append(s.n)
        return Box(x=1, y=2, w=3, h=4), None

    def forget(self, n):
        self.forgot.append(n)

    def learn(self, s, box):
        return self.window


def apps(front="Visual Studio Code", open_=True):
    main = Finder("Visual Studio Code")
    made = {}

    def make(app):
        made[app] = Finder(app)
        return made[app]
    return StepApps(main, "Visual Studio Code", make, lambda w: w == front, lambda w: object() if open_ else None), main, made


def test_a_step_app_survives_a_file_round_trip():
    t = tutorial(step(app="Google Chrome"))
    again = parse_text(render(t))
    assert again.steps[0].app == "Google Chrome"
    assert render(tutorial(step())).count("app:") == 1      # only the tutorial's own


def test_each_step_is_found_in_its_own_app():
    r, main, made = apps(front="Google Chrome")
    assert r.locate(step(app="Google Chrome"))[0] is not None
    assert made["Google Chrome"].asked == [1] and main.asked == []
    assert r.last_els == []                         # never kept as the main app's
    r.locate(step(2, app="google chrome"))
    assert len(made) == 1                           # one finder per app, whatever the spelling's case


def test_a_step_app_not_in_front_says_where_to_go_and_looks_for_nothing():
    r, main, made = apps(front="Visual Studio Code")
    assert r.locate(step(app="Google Chrome")) == (None, None)
    assert r.last_extra == {"switch_to": "Google Chrome", "app_open": True}
    assert made["Google Chrome"].asked == []
    r, main, made = apps(front="Other", open_=False)
    r.locate(step())
    assert r.last_extra == {"switch_to": "Visual Studio Code", "app_open": False}
    assert main.asked == []


def test_a_switch_step_needs_no_control():
    r, main, made = apps(front="Other")
    assert r.locate(step(action="switch_app", label="Terminal", kind="window")) == (None, None)
    assert "switch_to" not in r.last_extra


def test_forget_and_learn_reach_the_right_finder():
    r, main, made = apps(front="Terminal")
    r.locate(step(app="Terminal"))
    r.forget(1)
    assert main.forgot == [1] and made["Terminal"].forgot == [1]
    assert r.learn(step(app="Terminal"), Box(x=0, y=0, w=1, h=1)) == "Terminal"
    assert r.learn(step(), Box(x=0, y=0, w=1, h=1)) == "Visual Studio Code"


def _player(locator, *steps):
    return Player(Session(tutorial(*(steps or (step(app="Tool"),)))), locator=locator)


def test_the_card_says_switch_or_offers_use_this_window():
    r, _, _ = apps(front="x")
    p = _player(r)
    msgs = p.apply_located(p.locate_current())
    g = [x for x in msgs if x.type == "guide"][0]
    assert "Switch to it" in g.card.detail and "use_window" not in g.card.actions and g.card.dev_hint is None

    r, _, _ = apps(front="x", open_=False)
    p = _player(r)
    g = [x for x in p.apply_located(p.locate_current()) if x.type == "guide"][0]
    assert "use_window" in g.card.actions
    chosen = []
    p.use_window = lambda app: chosen.append(app) or "Some Program"
    assert p.handle({"type": "use_window"})[-1].text == "Using Some Program as Tool."
    assert chosen == ["Tool"]


def test_do_it_goes_to_the_steps_own_executor():
    class Ex:
        def __init__(self):
            self.ran = 0

        def run(self, ops):
            self.ran += 1

    ex = Ex()
    p = Player(Session(tutorial(step(app="Tool", action="shortcut", label="Save", kind="button"))))
    p.session.tutorial.steps[0].params["keys"] = ["Ctrl", "S"]
    p.executor_for = lambda s: ex if s.app == "Tool" else None
    p.handle({"type": "do_it"})
    assert ex.ran == 1
    p.executor_for = lambda s: None
    assert "isn't available" in p.handle({"type": "do_it"})[0].text


def test_short_names_for_vs_code_find_it():
    assert is_vscode("VS Code") and is_vscode("vscode") and not is_vscode("Visual Studio")
    assert pick([Win(1, "a - Visual Studio Code", (0, 0, 9, 9))], "VS Code").hwnd == 1


def test_compile_keeps_other_apps_and_drops_the_main_one():
    raw = {"title": "T", "app": "VS Code", "steps": [
        {"title": "A", "app": "vs code", "action": "click", "target": {"label": "A", "kind": "button"}, "check": "c", "source": {"anchor": "#a"}, "confidence": "high"},
        {"title": "B", "app": "Google Chrome", "action": "click", "target": {"label": "B", "kind": "button"}, "check": "c", "source": {"anchor": "#a"}, "confidence": "high"}]}
    tut, errors = to_tutorial(raw, Evidence(type="text", url=None, hash="h", title="T", items=[]))
    assert not errors
    assert [s.app for s in tut.steps] == [None, "Google Chrome"]


# ---------- a model's look at a stuck rule check ----------
class Clock:
    t = 100.0

    def __call__(self):
        return self.t


def _tracker(st, answer="done"):
    from engine.live import capture
    asked = []

    def glimmer(s, png):
        asked.append(s.n)
        return Verdict(answer, "glimmer")
    clock = Clock()
    pictures = [Image.new("RGB", (64, 64), "white"), Image.new("RGB", (64, 64), "black")]
    t = Tracker(tutorial(st), "Visual Studio Code", None, lambda w: [{"name": "x", "type": "Button"}], ladder=Ladder(glimmer=glimmer),
                grab=lambda s: pictures[0] if clock.t < 105 else pictures[1], clock=clock)
    t.current_n = 1
    return t, clock, asked


UIA_RULE = Verify(uia={"name": "Never Appears", "type": "Window"})


def test_a_stuck_rule_check_reaches_a_model_once_the_window_changed():
    st = step(verify=UIA_RULE)
    t, clock, asked = _tracker(st)
    snap = t.snapshot()
    assert t.check(st, snap).result == "not_yet" and not asked      # the baseline
    clock.t = 106
    assert t.check(st, t.snapshot()).result == "not_yet" and not asked   # changed, but not stuck yet
    clock.t = 100 + STUCK_S + 1
    v = t.check(st, t.snapshot())
    assert v.done and v.stage == "glimmer" and asked == [1]


def test_only_a_models_done_overrules_the_rule():
    st = step(verify=UIA_RULE)
    t, clock, asked = _tracker(st, answer="wrong")
    t.check(st, t.snapshot())
    clock.t = 100 + STUCK_S + 1
    v = t.check(st, t.snapshot())
    assert asked == [1] and v.stage == "rule" and v.result == "not_yet"


def test_exact_facts_are_never_overruled():
    for rule in (Verify(file={"path": "a.txt", "contains": "x"}), Verify(uia={"type": "Edit", "value_contains": "x"})):
        st = step(verify=rule)
        t, clock, asked = _tracker(st)
        t.check(st, t.snapshot())
        clock.t = 100 + STUCK_S + 1
        assert not t.check(st, t.snapshot()).done and not asked


def test_a_step_ahead_and_no_models_cost_nothing():
    st = step(verify=UIA_RULE)
    t, clock, asked = _tracker(st)
    t.current_n = 2
    clock.t = 100 + STUCK_S + 1
    t.check(st, t.snapshot())
    assert not asked
    t2 = Tracker(tutorial(st), "x", None, lambda w: [{"name": "x"}], grab=lambda s: 1 / 0, clock=clock)
    t2.current_n = 1
    assert t2.check(st, t2.snapshot()).result == "not_yet"     # never even takes a picture


def test_a_switch_step_is_done_when_that_app_is_in_front():
    st = step(action="switch_app", label="Terminal", kind="window")
    t, _, _ = _tracker(st)
    t.front_is = lambda app: False
    assert t.check(st, t.snapshot()).result == "not_yet"
    t.front_is = lambda app: app == "Terminal"
    assert t.check(st, t.snapshot()).done


def test_a_step_in_another_app_is_only_shown_to_a_model_while_in_front():
    st = step(app="Tool")
    t, clock, asked = _tracker(st)
    t.front_is = lambda app: False
    t.check(st, t.snapshot())
    clock.t = 106
    assert not t.check(st, t.snapshot()).done and not asked
    t.front_is = lambda app: True
    t.gate_for = lambda app: "secret title"
    clock.t = 112
    assert not t.check(st, t.snapshot()).done and not asked
    t.gate_for = lambda app: None
    clock.t = 118
    assert t.check(st, t.snapshot()).done and asked == [1]


def test_a_tutorials_other_apps_may_be_watched_by_a_model_but_no_others():
    other = step(2, action="wait", label="Secret App", kind="window")
    named = step(3, app="Tool", action="wait", label="Tool", kind="window")
    t = Tracker(tutorial(step(), other, named), "Visual Studio Code", None, lambda w: [])
    assert t._kept_here(other) == "it isn't the tutorial's app"
    assert t._kept_here(named) is None


# ---------- a model's look at a box found by sight ----------
SHOT = (Image.new("RGB", (800, 600), "white"), (100, 50), 1.0)
BOX = Box(x=200, y=100, w=40, h=20)


def _check(results, clock=None):
    calls, later = [], []

    def stage(s, png, text=None, tag=None):
        calls.append((text, tag))
        r = results.pop(0)
        if isinstance(r, Exception):
            raise r
        return Verdict(r, why="Two View")
    return BoxCheck("App", [stage], lambda: SHOT, clock=clock or Clock(), start=later.append), calls, later


def test_the_picture_shows_the_box_in_red_and_enlarged():
    import io
    png = picture(SHOT[0], SHOT[1], BOX)
    img = Image.open(io.BytesIO(png)).convert("RGB")
    assert img.width > 400
    assert (255, 0, 0) in set(img.getdata())


def test_box_check_waits_then_answers():
    c, calls, later = _check(["wrong"])
    st = step()
    assert c.say(st, "Front", BOX) == ("wait", "")
    assert c.say(st, "Front", BOX) == ("wait", "")
    later.pop()()
    assert c.say(st, "Front", BOX) == ("no", "Two View")
    assert len(calls) == 1 and calls[0][1] == "box-step-1" and "Front" in calls[0][0]


def test_box_check_shows_the_box_when_the_model_is_slow_or_silent():
    clock = Clock()
    c, calls, later = _check(["wrong"], clock)
    assert c.say(step(), "Front", BOX)[0] == "wait"
    clock.t += WAIT_S + 1
    assert c.say(step(), "Front", BOX)[0] == "unsure"
    later.pop()()
    assert c.say(step(), "Front", BOX)[0] == "no"       # a late "no" still takes it away
    c, _, later = _check([RuntimeError("down")])
    c.say(step(), "Front", BOX)
    later.pop()()
    assert c.say(step(), "Front", BOX)[0] == "unsure"


def test_box_check_stops_when_it_must_stay_here_or_has_looked_enough():
    assert BoxCheck("App", [lambda *a, **k: None], lambda: None).say(step(), "Front", BOX)[0] == "unsure"
    assert BoxCheck("App", [None, None], lambda: SHOT).say(step(), "Front", BOX)[0] == "unsure"
    c, calls, later = _check(["done"] * 9)
    for i in range(MAX_LOOKS + 2):
        c.say(step(), "Front", Box(x=200 + i, y=100, w=40, h=20))
    assert len(later) == MAX_LOOKS


class Vision:
    last_how, last_conf, last_line, last_route = "vision", "high", None, None

    def __init__(self):
        self.rejected = []

    def find(self, s, label=None, **kw):
        return BOX

    def reject(self, n, label, shown):
        self.rejected.append((n, label, shown))


class NoUia:
    window = "App"
    last_how = "not found"
    last_extra: dict = {}

    def locate(self, s, label=None):
        return None, None


class Said:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.asked = 0

    def say(self, s, label, box):
        self.asked += 1
        return self.answers.pop(0)

    def forget(self, n):
        pass


def test_the_finder_holds_a_box_till_the_second_look_and_drops_a_wrong_one():
    v, said = Vision(), Said(("wait", ""), ("yes", ""))
    r = Resolver(NoUia(), vision=v, box_check=said)
    assert r.locate(step(label="Front")) == (None, None)
    assert "second look" in r.last_how
    assert r.locate(step(label="Front"))[0] == BOX

    v, said = Vision(), Said(("no", "Two View"))
    r = Resolver(NoUia(), vision=v, box_check=said)
    assert r.locate(step(label="Front"))[0] is None
    assert v.rejected == [(1, "Front", "Two View")] and "Two View" in r.last_how


def test_geometry_gets_no_second_look():
    said = Said()
    r = Resolver(NoUia(), vision=Vision(), box_check=said)
    assert r.locate(step(action="pick", label="Edge", kind="edge"))[0] == BOX
    assert said.asked == 0
