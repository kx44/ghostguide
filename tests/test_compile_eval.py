"""The score against gold: plain code, so every rule is tested here without a model."""
from pathlib import Path

from engine.basefile.parse import parse_file
from engine.compile import eval as ev
from engine.schema.tutorial import Step, Tutorial, TutorialMeta

GOLD_MUG = Path("tutorials/mug-solidworks.md")
GOLD_VS = Path("tutorials/youtube-clone-vscode.md")


def _step(n, action="click", label="Save", title=None, **params):
    return Step(n=n, title=title or label, action=action, target={"label": label, "kind": "button"}, params=params,
                check="done", source={"anchor": "#a"}, confidence="high")


def _tut(steps):
    return Tutorial(meta=TutorialMeta(title="t", app="a", source={"type": "text"}), steps=steps)


def test_gold_against_itself_is_perfect():
    for path in (GOLD_MUG, GOLD_VS):
        t = parse_file(path)
        s = ev.score(t, t)
        assert s["raw"]["f1"] == 1.0 and not s["raw"]["missed"] and not s["raw"]["extra"]
        assert s["details"]["action"] == 1.0


def test_empty_compile_scores_zero():
    gold = parse_file(GOLD_VS)
    s = ev.score(_tut([_step(1, label="Nothing like it")]), gold)
    assert s["raw"]["matched"] == 0 and s["raw"]["f1"] == 0.0
    assert len(s["raw"]["missed"]) == len(gold.steps)


def test_steps_out_of_order_do_not_all_match():
    gold = _tut([_step(1, label="Alpha"), _step(2, label="Bravo"), _step(3, label="Charlie")])
    compiled = _tut([_step(1, label="Charlie"), _step(2, label="Bravo"), _step(3, label="Alpha")])
    assert ev.score(compiled, gold)["raw"]["matched"] == 1


def test_missing_and_extra_steps_lower_recall_and_precision():
    gold = _tut([_step(1, label="Alpha"), _step(2, label="Bravo")])
    compiled = _tut([_step(1, label="Alpha"), _step(2, label="Zulu"), _step(3, label="Yankee")])
    raw = ev.score(compiled, gold)["raw"]
    assert raw["matched"] == 1 and raw["missed"] == [2] and raw["extra"] == [2, 3]
    assert round(raw["recall"], 2) == 0.5 and round(raw["precision"], 2) == 0.33


def test_typed_text_decides_type_steps():
    gold = _tut([_step(1, "type", "Editor", value="<div class='a'></div>")])
    near = _tut([_step(1, "type", "Editor", value="<div  class='a'>\n</div>")])
    wrong = _tut([_step(1, "type", "Editor", value="body { margin: 0 }")])
    assert ev.score(near, gold)["details"]["typed_exact"] == 1.0
    assert ev.score(wrong, gold)["raw"]["matched"] == 0


def test_fair_never_changes_raw_and_only_uses_the_list():
    gold = _tut([_step(1, label="Alpha"), _step(2, "pick", "Added line"), _step(3, label="Bravo")])
    compiled = _tut([_step(1, label="Alpha"), _step(2, label="Bravo")])
    diff = {"differences": [{"step": 2, "why": "x", "missing_ok": True}]}
    s = ev.score(compiled, gold, differences=diff)
    assert s["raw"]["missed"] == [2] and round(s["raw"]["recall"], 2) == 0.67    # raw still counts it as missed
    assert s["fair"]["missed"] == [] and s["fair"]["recall"] == 1.0
    assert s == ev.score(compiled, gold, differences=diff)                       # same answer every run
    assert ev.score(compiled, gold)["raw"] == s["raw"]


def test_extra_ok_only_forgives_the_named_action_beside_the_step():
    gold = _tut([_step(1, "draw_line", "Origin"), _step(2, label="Bravo")])
    two_lines = _tut([_step(1, "draw_line", "Origin"), _step(2, "draw_line", "Second bit"), _step(3, label="Bravo")])
    a_click = _tut([_step(1, "draw_line", "Origin"), _step(2, "click", "Second bit"), _step(3, label="Bravo")])
    diff = {"differences": [{"step": 1, "why": "x", "extra_ok": {"action": "draw_line"}}]}
    assert ev.score(two_lines, gold, differences=diff)["fair"]["precision"] == 1.0
    assert ev.score(a_click, gold, differences=diff)["fair"]["extra"] == [2]


def test_alternative_label_only_counts_in_fair():
    gold = _tut([_step(1, label="Sketch1", title="Select the sketch")])
    compiled = _tut([_step(1, "pick", "Outer edge", title="Select the outer edge")])
    diff = {"differences": [{"step": 1, "why": "x", "labels": ["outer edge"], "actions": ["click", "pick"]}]}
    s = ev.score(compiled, gold, differences=diff)
    assert s["raw"]["matched"] == 0 and s["fair"]["matched"] == 1


def test_the_frozen_mug_list_names_real_gold_steps():
    diff = ev.load_differences(GOLD_MUG)
    gold = parse_file(GOLD_MUG)
    assert {d["step"] for d in diff["differences"]} == {6, 10, 17, 29}
    assert all(1 <= d["step"] <= len(gold.steps) and d["why"] for d in diff["differences"])
    assert ev.load_differences(GOLD_VS) is None


def test_gold_is_found_by_source_url():
    assert ev.find_gold("https://www.youtube.com/watch?v=rhPSo4_Tgi0").name == GOLD_VS.name
    assert ev.find_gold("https://www.engineersrule.com/10-steps-creating-first-product-solidworks/").name == GOLD_MUG.name
    assert ev.find_gold("https://example.com/nope") is None and ev.find_gold(None) is None


def test_score_records_which_gold_it_used(tmp_path):
    s = ev.score_files(GOLD_VS, GOLD_VS)
    assert s["gold_file"] == GOLD_VS.name and len(s["gold_sha"]) == 16
    assert "raw:" in ev.report(s)
