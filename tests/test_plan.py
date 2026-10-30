import pytest

from engine import config
from engine.basefile.parse import parse_file, parse_text
from engine.live.plan import Planner, click_type
from engine.schema.messages import Box, Display, Line

VS = parse_file(config.TUTORIALS / "youtube-clone-vscode.md")
MUG = parse_file(config.TUTORIALS / "mug-solidworks.md")
BOX = Box(x=100, y=100, w=40, h=20)
SCREEN = [Display(id=0, x=0, y=0, w=1920, h=1080, primary=True)]


def plan(tut, n, box=BOX, line=None, displays=SCREEN):
    return Planner(tut).plan(tut.step(n), box, line, displays, "dark")


def test_action_to_style_vscode():
    p = Planner(VS)
    styles = {s.n: p.style(s) for s in VS.steps}
    assert styles[1] == "outline"           # New File, first time
    assert styles[2] == "code_card" and styles[6] == "keycaps"
    assert styles[7] == "path_chips" and styles[8] == "signal_card"
    assert styles[14] == "outline" and styles[19] == "beacon"   # index.html tab again → repeat
    assert styles[16] == "beacon" and styles[21] == "beacon"    # gold file: repeat_of 14


def test_click_type_first_time_only():
    p = Planner(MUG)
    rights = [s.n for s in MUG.steps if (click_type(s.params) or {}).get("button") == "right"]
    doubles = [s.n for s in MUG.steps if (click_type(s.params) or {}).get("count") == 2]
    assert doubles and rights
    g = Planner(MUG).plan(MUG.step(doubles[0]), BOX)
    assert g.style == "click_type" or "click_type" in g.extra
    assert g.extra["click_type"]["label"] == "Double-click"
    g7 = plan(VS, 7)
    assert g7.style == "path_chips" and g7.extra["click_type"]["button"] == "right"


def test_click_type_parsing():
    assert click_type({"click_type": "right"})["label"] == "Right-click"
    assert click_type({"click_type": "ctrl"})["modifiers"] == ["Ctrl"]
    assert click_type({"click_type": "ctrl+right"})["label"] == "Ctrl + Right-click"
    assert click_type({}) is None and click_type({"click_type": "left"}) is None


def test_code_card_and_card():
    g = plan(VS, 2)
    assert g.style == "code_card" and g.extra["value"] == "index.html" and g.extra["then_key"] == "Enter"
    assert g.card.detail == "Type “index.html”, then press Enter."
    assert g.card.meta == "Step 2 of 23 · Visual Studio Code" and "show_me" in g.card.actions
    assert "do_it" not in g.card.actions       # phase 4
    g4 = plan(VS, 4)
    assert g4.extra["multiline"] and g4.card.detail == "Copy this, or type it, in index.html, inside <body>."
    assert plan(VS, 4, box=None).style == "code_card"     # no target yet: the card still carries the code


def test_keycaps_and_menu_path_extras():
    g = plan(VS, 6)
    assert g.extra["keys"] == ["Ctrl", "S"] and g.card.detail == "Press Ctrl + S."
    g7 = plan(VS, 7)
    assert g7.extra["path"] == ["index.html (right-click)", "Open with Live Server"] and g7.extra["path_done"] == 0
    assert g7.extra["shortcut"] == "Alt+L Alt+O" and g7.card.low_confidence


def test_no_target_falls_back_to_card_but_keeps_extras():
    g = plan(VS, 7, box=None)
    assert g.style == "card" and g.extra["path"] and g.card and "show_me" not in g.card.actions
    g19 = plan(VS, 19, box=None)       # beacon without a box → full card
    assert g19.style == "card" and g19.card is not None
    assert plan(VS, 6, box=None).style == "keycaps"      # keycaps need no target
    assert plan(VS, 8, box=None).style == "signal_card"


def test_beacon_gets_a_compact_card_with_up_next():
    g = plan(VS, 19)
    assert g.style == "beacon" and g.card.compact and g.card.actions == ["next"]
    assert g.card.title == "Switch to index.html" and g.card.up_next == "Add the video duration"
    assert plan(VS, 12).card.up_next == "Name it styles.css"     # after New File: what to name it
    assert plan(VS, 23).card.compact is False


def test_wait_says_press_next_until_checks_exist():
    g = plan(VS, 8, box=None)
    assert g.card.actions == ["next"] and g.card.detail == "When it has loaded, press Next."


def test_lines_and_repeats():
    p = Planner(MUG)
    lines = [s for s in MUG.steps if s.action in ("draw_line", "drag")]
    first = lines[0]
    ln = Line(start=(10, 10), end=(200, 10))
    g = p.plan(first, BOX, ln, SCREEN)
    assert g.style == "ghost_line" and g.line is not None and g.to_wire()["line"] == {"from": [10, 10], "to": [200, 10]}
    assert p.plan(first, BOX, None, SCREEN).style == "outline"       # no path pinned → point at the box
    sm = p.show_me(first, BOX, ln)
    assert sm.path == [(10, 10), (200, 10)] and sm.click == "none"


def test_offscreen():
    g = plan(VS, 1, box=Box(x=2500, y=500, w=20, h=20))
    assert g.style == "offscreen" and g.extra["direction"] == "right" and g.extra["original_style"] == "outline"
    assert g.extra["edge_point"] == [1920 - 28, 510] and g.card.title.startswith("Bring")
    g2 = plan(VS, 1, box=Box(x=500, y=-300, w=20, h=20))
    assert g2.extra["direction"] == "up"
    # two monitors side by side: the box is on the second one, so it is on screen
    two = SCREEN + [Display(id=1, x=1920, y=0, w=2560, h=1440)]
    assert plan(VS, 1, box=Box(x=2500, y=500, w=20, h=20), displays=two).style == "outline"


def test_suggested_values_labelled():
    sug = [s for s in MUG.steps if "suggested" in s.params]
    g = Planner(MUG).plan(sug[0], BOX)
    assert g.card.suggested and "mm" in g.card.suggested


def test_every_step_of_both_gold_files_plans():
    for tut in (VS, MUG):
        p = Planner(tut)
        for s in tut.steps:
            for box in (BOX, None):
                g = p.plan(s, box, None, SCREEN, "light")
                assert g.step.n == s.n and g.style
                assert g.card is not None and g.card.compact == (g.style in ("beacon", "static_line"))


def test_look_step_card_only_with_next():
    look = [s for s in MUG.steps if s.action == "look"][0]
    g = Planner(MUG).plan(look, None)
    assert g.style == "card" and g.card.actions == ["next"]
