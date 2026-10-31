from pathlib import Path

import pytest

from engine.basefile.parse import ParseError, parse_file, parse_text
from engine.basefile.render import render_text
from engine.basefile.validate import validate_file, validate_tutorial

ROOT = Path(__file__).resolve().parent.parent
GOLD = sorted((ROOT / "tutorials").glob("*.md"))

MINI = """---
title: Mini
app: Visual Studio Code
source: {type: video, url: "https://example.com/v"}
---

# Part A — Start

## Step 1 — New file
```yaml
action: click
target: {label: New File, kind: button, where: "Explorer header"}
check: "Filename box"
source: {t: "01:39-01:41"}
confidence: high   # comment kept
```
## Step 2 — Save
```yaml
action: shortcut
target: {label: Save, kind: button}
params: {keys: [Ctrl, S]}
check: "Saved"
source: {t: "03:40"}
repeat_of: 1
```
"""


def test_gold_files_present():
    assert {p.name for p in GOLD} >= {"mug-solidworks.md", "youtube-clone-vscode.md"}


@pytest.mark.parametrize("path", GOLD, ids=lambda p: p.name)
def test_gold_round_trip_is_byte_exact(path):
    text = path.read_text(encoding="utf-8")
    assert render_text(parse_file(path)) == text


@pytest.mark.parametrize("path", GOLD, ids=lambda p: p.name)
def test_gold_validates(path):
    r = validate_file(path)
    assert r.ok, r.errors


def test_gold_step_counts_and_verify():
    vs = parse_file(ROOT / "tutorials/youtube-clone-vscode.md")
    mug = parse_file(ROOT / "tutorials/mug-solidworks.md")
    assert len(vs.steps) == 23 and len(mug.steps) == 45
    assert vs.meta.gold and mug.meta.gold
    assert all(s.verify is not None for s in vs.steps)     # every step has a hint
    assert sum(s.verify is not None for s in mug.steps) == 26
    s14 = vs.step(14).verify.uia_checks()[0]
    assert (s14.name_contains, s14.type, s14.selected) == ("index.html", "TabItem", True)
    assert [f.path for f in vs.step(23).verify.file_checks()] == ["styles.css"]


def test_parts_and_titles():
    t = parse_text(MINI)
    assert t.step(1).part == "Part A — Start"
    assert t.step(2).title == "Save"
    assert t.step(1).style == 1 and t.step(2).style == 6


def test_edited_step_is_re_rendered_and_round_trips():
    t = parse_text(MINI)
    t.step(1).check = "Inline filename box"
    out = render_text(t)
    assert "Inline filename box" in out
    assert "# comment kept" not in out               # edited block is re-dumped
    again = parse_text(out)
    assert again.step(1).yaml_data() == t.step(1).yaml_data()
    assert again.step(2).yaml_data() == t.step(2).yaml_data()
    assert render_text(again) == out                  # stable after one pass


def test_multiline_values_render_as_blocks():
    t = parse_text(MINI)
    t.step(1).params = {"value": "<div>\n</div>\n"}
    t.step(1).action = "type"
    out = render_text(t)
    assert "value: |" in out
    assert parse_text(out).step(1).params["value"] == "<div>\n</div>\n"


@pytest.mark.parametrize("bad, message", [
    (MINI.replace("action: click", "action: tap"), "action"),
    (MINI.replace("kind: button, where", "kind: widget, where"), "kind"),
    (MINI.replace("check: \"Filename box\"\n", ""), "check"),
    (MINI.replace("confidence: high", "confidence: high\nbogus: 1"), "bogus"),
    (MINI.replace("```yaml\naction: click", "```yaml\naction: [click"), "bad YAML"),
    (MINI.replace("---\ntitle", "title"), "frontmatter"),
    (MINI.replace("## Step 1 — New file\n", ""), "heading"),
    (MINI + "\nsome stray prose\n", "unexpected text"),
])
def test_parse_errors_name_the_problem(bad, message):
    with pytest.raises(ParseError) as e:
        parse_text(bad, "mini.md")
    assert message in str(e.value)


def _errors(text):
    return validate_tutorial(parse_text(text)).errors


def test_rules():
    assert _errors(MINI) == []
    assert any("confidence" in e for e in _errors(MINI.replace("repeat_of: 1", "")))
    assert any("earlier step" in e for e in _errors(MINI.replace("repeat_of: 1", "repeat_of: 2")))
    assert any("mm:ss" in e for e in _errors(MINI.replace('t: "03:40"', 't: "3m40s"')))
    assert any("needs source.t" in e for e in _errors(MINI.replace('{t: "03:40"}', '{anchor: "#s"}')))
    assert any("params.keys" in e for e in _errors(MINI.replace("params: {keys: [Ctrl, S]}\n", "")))
    assert any("screen position" in e for e in _errors(MINI.replace("params: {keys: [Ctrl, S]}", "params: {keys: [Ctrl, S], box: [1, 2, 3, 4]}")))
    assert any("type needs" in e for e in _errors(MINI.replace("action: shortcut", "action: type")))


def test_numbering_must_be_sequential():
    assert any("1..N" in e for e in _errors(MINI.replace("## Step 2", "## Step 3")))


def test_verify_rules():
    with_verify = MINI.replace('check: "Saved"', 'check: "Saved"\nverify: {uia: {type: Widget}}')
    with pytest.raises(ParseError, match="UIA control type"):
        parse_text(with_verify)
    with pytest.raises(ParseError, match="verify needs"):
        parse_text(MINI.replace('check: "Saved"', 'check: "Saved"\nverify: {}'))
    abs_path = MINI.replace('check: "Saved"', 'check: "Saved"\nverify: {file: {path: ../x.html, contains: a}}')
    assert any("relative" in e for e in _errors(abs_path))
