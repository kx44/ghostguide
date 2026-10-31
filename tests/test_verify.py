"""Check ladder (live/verify.py), the catch-up scan (session.scan) and smart Next in the player, over a fake
VS Code + Chrome: element dumps built from a small state, files in a temp folder."""
from pathlib import Path

from PIL import Image

from engine.basefile.parse import parse_file
from engine.live.player import Player
from engine.live.session import Session
from engine.live.verify import (Ladder, Snapshot, Tracker, Verdict, lasting, rule_check, typed_lines_present)
from engine.models.glimmer import parse_answer
from engine.schema.tutorial import Step, UiaCheck

ROOT = Path(__file__).resolve().parent.parent
VS = parse_file(ROOT / "tutorials/youtube-clone-vscode.md")
APP = "youtube-clone - Visual Studio Code"


class Screen:
    """What's on screen: VS Code tabs, the active editor's text, the filename box; Chrome's tab and address."""

    def __init__(self, folder: Path):
        self.folder = folder
        self.tabs: list[str] = []
        self.active: str | None = None
        self.text: dict[str, str] = {}        # editor buffers (unsaved too)
        self.filename_box = False
        self.chrome_tabs: list[str] = ["Inbox"]
        self.url = "example.com"

    def dump(self, window: str) -> list[dict]:
        if "chrome" in window.casefold():
            return ([{"name": t, "type": "TabItem", "rect": [0, 0, 50, 20], "window": "x - Google Chrome"}
                     for t in self.chrome_tabs]
                    + [{"name": "Address and search bar", "type": "Edit", "value": self.url, "rect": [0, 30, 300, 20]}])
        els = [{"name": "Explorer Section: youtube-clone", "type": "Button", "rect": [0, 100, 400, 40]}]
        for t in self.tabs:
            els.append({"name": t, "type": "TabItem", "selected": t == self.active, "rect": [500, 0, 100, 40]})
        if self.active:
            els.append({"name": self.active, "type": "Edit", "value": self.text.get(self.active, ""), "rect": [600, 200, 900, 30]})
        if self.filename_box:
            els.append({"name": "Type file name. Press Enter to confirm or Escape to cancel.", "type": "Edit",
                        "value": "", "rect": [10, 160, 380, 30]})
        return els

    # doing tutorial steps
    def new_file(self):
        self.filename_box = True

    def name(self, f: str):
        self.filename_box = False
        (self.folder / f).write_text("", encoding="utf-8")
        self.tabs.append(f)
        self.active = f
        self.text[f] = ""

    def type(self, f: str, code: str):
        self.text[f] = self.text.get(f, "") + "\n" + code

    def save(self):
        for f, t in self.text.items():
            (self.folder / f).write_text(t, encoding="utf-8")


def code(n: int) -> str:
    return str(VS.step(n).params.get("value", ""))


def tracker(screen: Screen, **kw) -> Tracker:
    return Tracker(VS, APP, screen.folder, screen.dump, **kw)


def snap(screen: Screen) -> Snapshot:
    return Snapshot(APP, screen.dump, screen.folder)


def do_part_a(sc: Screen, upto: int):
    """Steps 1..upto of the tutorial, as a person would leave the screen."""
    acts = {1: sc.new_file, 2: lambda: sc.name("index.html"), 3: lambda: sc.type("index.html", "<!DOCTYPE html>\n<head>\n<title>Document</title>\n</head>\n<body>\n</body>"),
            4: lambda: sc.type("index.html", code(4)), 5: lambda: sc.type("index.html", code(5)), 6: sc.save,
            7: lambda: setattr(sc, "url", "127.0.0.1:5501/index.html"), 8: lambda: sc.chrome_tabs.append("Document"),
            9: lambda: sc.type("index.html", code(9)), 10: lambda: sc.type("index.html", code(10)), 11: sc.save,
            12: sc.new_file, 13: lambda: sc.name("styles.css"), 14: lambda: setattr(sc, "active", "index.html"),
            15: lambda: sc.type("index.html", code(15)), 16: lambda: setattr(sc, "active", "styles.css"),
            17: lambda: sc.type("styles.css", code(17))}
    for n in range(1, upto + 1):
        acts[n]()


# ---------- rule check ----------
def test_rule_check_reads_tabs_editor_and_files(tmp_path):
    sc = Screen(tmp_path)
    assert rule_check(VS.step(2), snap(sc)).result == "not_yet"
    do_part_a(sc, 2)
    v = rule_check(VS.step(2), snap(sc))
    assert v.done and v.lasting                     # an open tab lasts
    do_part_a(sc, 3) if False else sc.type("index.html", "<!DOCTYPE html>")
    assert rule_check(VS.step(3), snap(sc)).done
    sc.type("index.html", '<div class="videos">\n  <section class="video-section">\n    <article class="video-container">')
    v = rule_check(VS.step(4), snap(sc))            # key line typed, closing tags not yet: not done
    assert v.result == "not_yet" and v.lasting and "not all" in v.why
    sc.type("index.html", "    </article>\n  </section>\n</div>")
    assert rule_check(VS.step(4), snap(sc)).done
    assert rule_check(VS.step(6), snap(sc)).result == "not_yet"     # not saved yet
    sc.type("index.html", code(5))
    sc.save()
    assert rule_check(VS.step(6), snap(sc)).done


def test_selected_tab_and_open_box_dont_last(tmp_path):
    sc = Screen(tmp_path)
    do_part_a(sc, 1)
    v = rule_check(VS.step(1), snap(sc))
    assert v.done and not v.lasting
    do_part_a(sc, 16)
    v14 = rule_check(VS.step(14), snap(sc))       # styles.css is selected now
    assert v14.result == "not_yet" and not v14.lasting


def test_editor_check_falls_back_to_disk_when_another_file_is_open(tmp_path):
    sc = Screen(tmp_path)
    do_part_a(sc, 13)                              # styles.css is the active editor; index.html saved at 11
    v = rule_check(VS.step(10), snap(sc))
    assert v.done and v.lasting                   # read from index.html on disk
    assert rule_check(VS.step(15), snap(sc)).result == "unknown"     # not in the file on disk, editor not open


def test_typed_lines_ignore_indent_and_auto_close():
    v = '<div class="a">\n  <p>x</p>\n</div>\n'
    assert typed_lines_present(v, '<body>\n<div class="a">\n<p>x</p>\n</div>\n</body>')
    assert typed_lines_present(v, '<div class="a"><p>x</p></div>')
    assert not typed_lines_present(v, '<div class="a">\n</div>')


def test_lasting_kinds():
    assert lasting(UiaCheck(type="TabItem", name_contains="index.html"))
    assert not lasting(UiaCheck(type="TabItem", name_contains="index.html", selected=True))
    assert lasting(UiaCheck(type="Edit", window="Visual Studio Code", value_contains="x"))
    assert not lasting(UiaCheck(type="Edit", name="Address and search bar", value_contains="x"))
    assert not lasting(UiaCheck(type="Edit", name_contains="Type file name"))


# ---------- trust guard ----------
def test_a_fact_already_true_at_the_start_proves_nothing(tmp_path):
    sc = Screen(tmp_path)
    sc.url = "127.0.0.1:5501/index.html"          # a Live Server tab left open from last time
    lad = Ladder()
    assert lad.rule(VS.step(7), snap(sc)).result == "unknown"
    sc.url = "example.com"
    assert lad.rule(VS.step(7), snap(sc)).result == "not_yet"
    sc.url = "127.0.0.1:5501/index.html"
    assert lad.rule(VS.step(7), snap(sc)).done      # seen false, now true: it happened during this run


# ---------- tracker: settle, wait, diff, models ----------
def test_typing_step_waits_until_you_stop_typing(tmp_path):
    sc = Screen(tmp_path)
    idle = [0.3]
    tr = tracker(sc, idle_s=lambda: idle[0])
    do_part_a(sc, 2)
    tr.check(VS.step(3), snap(sc))                 # seen false
    sc.type("index.html", "<!DOCTYPE html>")
    v = tr.check(VS.step(3), snap(sc))
    assert v.result == "not_yet" and v.stage == "settle"
    idle[0] = 2.0
    assert tr.check(VS.step(3), snap(sc)).done


def test_wait_step_done_once_the_window_settles(tmp_path):
    sc = Screen(tmp_path)
    t = [0.0]
    frames = [Image.new("L", (200, 100), 0)]
    tr = tracker(sc, grab=lambda step: frames[-1], clock=lambda: t[0])
    s8 = VS.step(8)
    assert tr.check(s8, snap(sc)).result == "not_yet"           # hint: no "Document" tab yet
    sc.chrome_tabs.append("Document")
    t[0] = 0.5
    assert tr.check(s8, snap(sc)).why == "just started"
    t[0] = 1.2
    assert tr.check(s8, snap(sc)).why == "still changing"       # first frame
    frames.append(Image.new("L", (200, 100), 200))
    t[0] = 2.0
    assert tr.check(s8, snap(sc)).why == "still changing"       # page still drawing
    t[0] = 3.0
    assert tr.check(s8, snap(sc)).why == "settling"
    t[0] = 3.6
    assert tr.check(s8, snap(sc)).done


def test_diff_says_not_yet_when_nothing_changed_and_asks_models_when_it_did(tmp_path):
    import copy
    tut = copy.deepcopy(VS)
    s1 = tut.step(1)
    s1.verify = None                              # a step without a hint
    frames = [Image.new("L", (200, 100), 0)]
    asked = []

    def glimmer(step, png):
        asked.append(step.n)
        return Verdict("done", "glimmer")
    sc = Screen(tmp_path)
    tr = Tracker(tut, APP, tmp_path, sc.dump, ladder=Ladder(glimmer=glimmer), grab=lambda st: frames[-1])
    assert tr.check(s1, snap(sc)).why == "baseline taken"
    assert tr.check(s1, snap(sc)).why == "nothing changed yet" and not asked     # no model call
    frames.append(Image.new("L", (200, 100), 255))
    assert tr.check(s1, snap(sc)).done and asked == [1]
    tr2 = Tracker(tut, APP, tmp_path, sc.dump, grab=lambda st: frames[-1])        # models off
    tr2.check(s1, snap(sc))
    frames.append(Image.new("L", (200, 100), 0))
    assert tr2.check(s1, snap(sc)).result == "unknown"


def test_model_answers_are_parsed():
    assert parse_answer('```json\n{"result": "done", "why": "tab open"}\n```').done
    assert parse_answer('{"result": "not yet"}').result == "not_yet"
    assert parse_answer("I think so").result == "unknown"
    assert parse_answer('{"result": "maybe"}').result == "unknown"


# ---------- catch-up scan ----------
def scan_from(sc: Screen, current: int, tr: Tracker | None = None) -> list[int]:
    s = Session(VS)
    s.current = current
    tr = tr or tracker(sc)
    return s.scan(tr.checker(snap(sc)))


def primed(sc: Screen) -> Tracker:
    tr = tracker(sc)
    tr.prime(snap(sc))          # at the start nothing is done: every fact is seen false once
    return tr


def test_catch_up_lands_after_the_steps_done_while_hidden(tmp_path):
    sc = Screen(tmp_path)
    tr = primed(sc)
    do_part_a(sc, 11)
    tr2 = tracker(sc)
    tr2.ladder = tr.ladder
    # hidden at 12, then did 12–15 (filename box closed again, index.html active with the links typed)
    do_part_a_from = [sc.new_file, lambda: sc.name("styles.css"), lambda: setattr(sc, "active", "index.html"),
                      lambda: sc.type("index.html", code(15))]
    for f in do_part_a_from:
        f()
    assert scan_from(sc, 12, tr2) == [12, 13, 14, 15]


def test_a_selected_tab_never_skips_work_you_didnt_do(tmp_path):
    sc = Screen(tmp_path)
    tr = primed(sc)
    do_part_a(sc, 13)                    # hidden at 13 and did only 13: styles.css open and selected
    # 14 (index.html selected) is false but doesn't last; 15 unreadable; 16 (styles.css selected) is true but
    # doesn't last either, so it can't stand in for 14–15; 17 says a lasting not-yet. Land on 14.
    assert scan_from(sc, 13, tr) == [13]


def test_nothing_done_while_hidden_stays_put(tmp_path):
    sc = Screen(tmp_path)
    tr = primed(sc)
    do_part_a(sc, 11)
    assert scan_from(sc, 12, tr) == []
    fresh = Screen(tmp_path / "x"); fresh.folder.mkdir()
    assert scan_from(fresh, 1, primed(fresh)) == []


def test_early_action_moves_past_an_unprovable_step(tmp_path):
    sc = Screen(tmp_path)
    tr = primed(sc)
    do_part_a(sc, 2)                      # step 1's box is closed again: only step 2's tab says 1 happened
    assert scan_from(sc, 1, tr) == [1, 2]


# ---------- smart Next in the player ----------
def player(sc: Screen, tr: Tracker) -> Player:
    p = Player(Session(VS), tracker=tr)
    p.handle({"type": "hello", "displays": [{"id": 0, "x": 0, "y": 0, "w": 1920, "h": 1080, "primary": True}]})
    return p


def test_player_moves_on_by_itself_and_never_undoes_back(tmp_path):
    sc = Screen(tmp_path)
    tr = primed(sc)
    p = player(sc, tr)
    assert p.apply_checked(p.check_round()) == []                 # nothing done yet
    sc.new_file()
    out = p.apply_checked(p.check_round())
    assert p.session.current == 2 and p.session.status(1) == "done"
    assert any(m.type == "toast" and m.text == "✓ Step 1 done" for m in out)
    sc.name("index.html")
    p.apply_checked(p.check_round())
    assert p.session.current == 3
    p.handle({"type": "back"})                                     # look at step 2 again
    assert p.apply_checked(p.check_round()) == [] and p.session.current == 2
    p.handle({"type": "next"})
    assert p.session.current == 3


def test_hidden_tracking_then_resume_catches_up_at_once(tmp_path):
    sc = Screen(tmp_path)
    tr = primed(sc)
    p = player(sc, tr)
    p.handle({"type": "hide"})
    do_part_a(sc, 3)
    r = p.check_round()
    assert p.apply_checked(r) == [] and p.session.current == 1     # hidden: remembered, not moved
    out = p.handle({"type": "resume"})
    assert p.session.current == 4 and not p.session.hidden
    assert any(m.type == "toast" and "Caught up" in m.text for m in out)


def test_wait_card_moves_on_by_itself():
    from engine.live.plan import Planner
    g = Planner(VS).plan(VS.step(8))
    assert g.card.actions == ["skip_wait"]


def test_a_fact_true_at_the_start_counts_once_you_act_on_the_step(tmp_path):
    sc = Screen(tmp_path)
    sc.url = "127.0.0.1:5501/index.html"           # left open from last time
    clicked = []
    tr = tracker(sc, acted=lambda n, since: n in clicked)
    tr.prime(snap(sc))
    assert tr.check(VS.step(7), snap(sc)).result == "unknown"
    clicked.append(7)                               # you right-clicked index.html / chose Open with Live Server
    v = tr.check(VS.step(7), snap(sc))
    assert v.done and "clicked" in v.why


def test_player_knows_when_you_clicked_a_drawn_target():
    from engine.live.inputs import InputEvent, Recent
    from engine.schema.messages import Box
    rec = Recent(clock=lambda: 100.0)
    p = Player(Session(VS), inputs=rec)
    p._drawn[7] = [Box(x=10, y=10, w=100, h=20)]
    rec.add(InputEvent("down", 50, 15, 99.0, "right"))
    assert p.acted_on(7, since=98.0) and not p.acted_on(7, since=99.5) and not p.acted_on(8, since=0)
    rec.add(InputEvent("down", 500, 500, 99.6, "left"))
    assert not p.acted_on(7, since=99.5)


def _weak_hint_tutorial():
    def s(n, title, check=None):
        return Step(n=n, title=title, action="click", target={"label": title, "kind": "button"}, check="done", source={"t": "00:01"},
                    verify={"uia": check} if check else None)
    from engine.schema.tutorial import Tutorial, TutorialMeta
    return Tutorial(meta=TutorialMeta(title="T", app="A", source={"type": "text"}), steps=[
        s(1, "Open document", {"name": "Part1", "type": "TreeItem"}),
        s(2, "Make the body", {"name": "Body", "type": "TreeItem"}),
        s(3, "Something unreadable"),
        s(4, "Make a plane", {"name_contains": "Plane", "type": "TreeItem"}),
    ])


def test_a_hint_true_before_the_step_came_up_cant_skip_work_or_vouch_for_it():
    from engine.live.session import Session
    tut = _weak_hint_tutorial()
    now = [0.0]
    els: list[dict] = []
    tr = Tracker(tut, APP, None, lambda w: els, clock=lambda: now[0])
    s = Session(tut)

    def round_():
        now[0] += 1
        sn = Snapshot(APP, lambda w: els, None, t=now[0])
        tr.verdicts(s, sn)
        s.apply_done(s.scan(tr.checker(sn)))

    els.append({"type": "Pane", "name": "app", "rect": [0, 0, 9, 9]})
    round_()                                   # no document: every hint is false
    assert s.current == 1
    els += [{"type": "TreeItem", "name": "Part1", "rect": [0, 0, 9, 9]},
            {"type": "TreeItem", "name": "Front Plane", "rect": [0, 0, 9, 9]}]     # the document brings its own Front Plane
    round_()
    assert s.current == 2
    round_()
    els.append({"type": "TreeItem", "name": "Body", "rect": [0, 0, 9, 9]})
    hidden = [e for e in els if e["type"] == "TreeItem"]
    for e in hidden:
        els.remove(e)
    round_()                                   # a tool's panel hides the tree, and its OK brings it back
    els += hidden
    round_()
    assert s.current == 3                      # the Plane hint came true long ago: no jump to the end
    assert tr.check(tut.step(4), Snapshot(APP, lambda w: els, None, t=now[0])).result == "unknown"
    s.current = 4
    round_()
    assert s.current == 4                      # and it can't vouch for its own step either
    els.append({"type": "TreeItem", "name": "Plane1", "rect": [0, 0, 9, 9]})
    round_()
    assert s.current == 4                      # still "Plane" all along: Next is the way on


def test_a_step_done_early_during_the_step_before_it_still_counts():
    from engine.live.session import Session
    tut = _weak_hint_tutorial()
    now = [0.0]
    els = [{"type": "Pane", "name": "app", "rect": [0, 0, 9, 9]}]
    tr = Tracker(tut, APP, None, lambda w: els, clock=lambda: now[0])
    s = Session(tut)

    def round_():
        now[0] += 1
        sn = Snapshot(APP, lambda w: els, None, t=now[0])
        tr.verdicts(s, sn)
        s.apply_done(s.scan(tr.checker(sn)))

    round_()
    els += [{"type": "TreeItem", "name": "Part1", "rect": [0, 0, 9, 9]}, {"type": "TreeItem", "name": "Body", "rect": [0, 0, 9, 9]}]
    round_()
    assert s.current == 3                      # both came true while step 1 was showing
