"""The Windows-only accuracy scripts keep their logic pure, so it is tested here on any OS."""
from pathlib import Path

from engine.basefile.parse import parse_file
from engine.schema.tutorial import UiaCheck
from tests.accuracy.glimmer_speed import CASES, build_prompt, load_cases, parse_verdict
from tests.accuracy.uia_coverage import eval_uia_check, match_target, summarise

ROOT = Path(__file__).resolve().parent.parent
VS = parse_file(ROOT / "tutorials/youtube-clone-vscode.md")
MUG = parse_file(ROOT / "tutorials/mug-solidworks.md")

ELEMENTS = [
    {"window": "index.html - youtube-clone - Visual Studio Code", "name": "index.html", "type": "TabItem",
     "rect": [100, 40, 90, 30], "selected": True},
    {"window": "index.html - youtube-clone - Visual Studio Code", "name": "styles.css", "type": "TabItem",
     "rect": [190, 40, 90, 30], "selected": False},
    {"window": "index.html - youtube-clone - Visual Studio Code", "name": "New File...", "type": "Button",
     "rect": [10, 80, 16, 16]},
    {"window": "index.html - youtube-clone - Visual Studio Code", "name": "Editor content", "type": "Edit",
     "rect": [300, 80, 800, 900], "value": '<a href="#" class="thumbnail" data-duration="12:24">'},
    {"window": "Document - Google Chrome", "name": "Address and search bar", "type": "Edit",
     "rect": [1200, 10, 600, 30], "value": "127.0.0.1:5501/index.html"},
    {"window": "x", "name": "Hidden", "type": "Button", "rect": [0, 0, 0, 0]},
]


def test_match_target_quality():
    assert match_target(VS.step(12), ELEMENTS)["quality"] == "exact"        # "New File..."
    m = match_target(VS.step(1), ELEMENTS)                                  # "New File" ⊂ "New File..."
    assert m["quality"] == "contains" and m["type_ok"]
    assert match_target(VS.step(14), ELEMENTS)["type"] == "TabItem"
    assert match_target(MUG.step(6), ELEMENTS)["quality"] == "n/a"         # canvas
    assert match_target(MUG.step(16), ELEMENTS)["quality"] == "none"


def test_verify_hints_against_elements():
    def holds(step):
        return all(eval_uia_check(c, ELEMENTS) for c in step.verify.uia_checks())
    assert holds(VS.step(14))          # index.html tab selected
    assert not holds(VS.step(16))      # styles.css tab not selected
    assert holds(VS.step(20))          # data-duration typed
    assert holds(VS.step(7))           # Chrome address bar
    assert eval_uia_check(UiaCheck(name="Gone", type="Window", exists=False), ELEMENTS)
    assert not eval_uia_check(UiaCheck(name="index.html", window="Chrome"), ELEMENTS)


def test_summary():
    rows = [{"n": 1, "title": "a", "label": "A", "target": {"quality": "exact"}, "verify": True},
            {"n": 2, "title": "b", "label": "B", "target": {"quality": "none"}, "verify": False},
            {"n": 3, "title": "c", "label": "C", "target": {"quality": "n/a"}}]
    s = summarise(rows)
    assert s["target_coverage"] == 0.5 and s["verify_coverage"] == 0.5 and s["canvas_targets"] == 1
    assert s["missed_targets"] == ["2: B"] and s["failed_verify"] == ["2: b"]


def test_glimmer_verdict_parser():
    assert parse_verdict('{"state": "done", "why": "tab open"}') == "done"
    assert parse_verdict('Sure! {"state": "not yet"}') == "not_yet"
    assert parse_verdict("The step looks WRONG: a cut instead of a boss") == "wrong"
    assert parse_verdict("no idea") == "unsure"
    assert "index.html open in editor" in build_prompt("Name it", "index.html open in editor")


def test_glimmer_cases_file():
    cases = load_cases(CASES)
    assert len(cases) >= 6 and {c["expect"] for c in cases} <= {"done", "not_yet", "wrong"}
