from engine import config
from engine.basefile.parse import parse_file
from engine.live.locate.pinned import Pin, Pins
from engine.live.locate.vscode import (Editor, editor_from, locate_in, new_file_box, norm, pitch_from_rows,
                                       target_line)
from engine.live.player import Player
from engine.live.session import Session

TUT = parse_file(config.TUTORIALS / "youtube-clone-vscode.md")
STEP = {s.n: s for s in TUT.steps}

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Document</title>
</head>
<body>
    <div class="videos">
      <section class="video-section">
        <article class="video-container">
          <a href="#" class="thumbnail">
            <img class="thumbnail-image" src="x" />
          </a>
          <div class="video-bottom-section">
            <a href="#">
              <img class="channel-icon" src="y" />
            </a>
          </div>
        </article>
      </section>
    </div>
</body>
</html>"""


def line_of(text, n):
    return text.split("\n")[n - 1].strip()


def test_where_hints_pick_the_right_line():
    assert target_line(HTML, "index.html, line 1") == 1
    assert line_of(HTML, target_line(HTML, "index.html, inside <body>")) == '<div class="videos">'
    assert line_of(HTML, target_line(HTML, 'index.html, inside <article class="video-container">')) == '<a href="#" class="thumbnail">'
    assert line_of(HTML, target_line(HTML, "index.html, after the thumbnail </a>")) == '<div class="video-bottom-section">'
    assert line_of(HTML, target_line(HTML, "index.html, inside .video-bottom-section after the icon link")) == "</div>"
    assert line_of(HTML, target_line(HTML, "index.html, inside <head>, before <title>")) == "<title>Document</title>"
    assert line_of(HTML, target_line(HTML, 'index.html, in <a href="#" class="thumbnail"> after class attribute')) == '<a href="#" class="thumbnail">'


def test_where_hints_top_end_and_fallback():
    css = "a {\n}\n\nb {\n}\n"
    assert target_line(css, "styles.css, top") == 1
    assert target_line(css, "styles.css, end") == 6           # the empty line after the last rule
    assert target_line("a {\n}", "styles.css, end") == 3
    assert target_line(HTML, "index.html, after <nothing-like-this>", caret_line=7) == 7
    assert target_line(HTML, None, caret_line=4) == 4


def test_norm_strips_vscode_key_hints():
    assert norm("Toggle Panel (Ctrl+J)") == "toggle panel"
    assert norm("Split Editor Right (Ctrl+\\) [Alt] Split Editor Down") == "split editor right"


def _els(**extra):
    els = [
        {"type": "Button", "name": "Explorer Section: youtube-clone", "rect": [94, 211, 523, 51]},
        {"type": "Tree", "name": "Files Explorer", "rect": [87, 262, 537, 900]},
        {"type": "TreeItem", "name": "index.html", "rect": [94, 262, 523, 40]},
        {"type": "TabItem", "name": "Explorer (Ctrl+Shift+E)", "rect": [13, 69, 66, 66], "selected": True},
        {"type": "TabItem", "name": "index.html", "rect": [634, 64, 214, 56], "selected": True},
        {"type": "TabItem", "name": "styles.css", "rect": [848, 64, 214, 56], "selected": False},
        {"type": "Group", "name": "index.html", "rect": [634, 161, 1396, 713]},
        {"type": "Edit", "name": "index.html", "rect": [756, 742, 1415, 35], "value": HTML},
        {"type": "Edit", "name": "Terminal 1", "rect": [1229, 969, 14, 32], "value": ""},
        {"type": "Button", "name": "Ln 18, Col 39", "rect": [1632, 1486, 141, 44]},
    ]
    return els + extra.get("more", [])


def test_editor_from_dump():
    ed = editor_from(_els())
    assert ed.file == "index.html" and ed.caret_line == 18 and ed.caret_top == 742 and ed.left == 756
    assert ed.right == 634 + 1396 - 120
    b = ed.line_box(8)
    assert b.y == 742 - 10 * 35 - 2 and b.h == 39 and b.x == 750


def test_unfocused_editor_places_lines_from_the_top_when_the_file_fits():
    parked = {"Edit": [634, 161, 1175, 2], "Group": [634, 161, 1396, 1300]}     # tall enough for all 24 lines
    els = [{**e, "rect": parked[e["type"]]} if e.get("name") == "index.html" and e["type"] in parked else e
           for e in _els()]
    ed = editor_from(els)
    assert not ed.focused and ed.scroll_known and ed.top == 161 and ed.caret_top == 161
    box, _, how = locate_in(STEP[4], els, ed)                         # inside <body>: line 8
    assert how == "editor line 8 (editor not focused)" and box.y == round(161 + 7 * 56 * 0.62) - 2
    long = [e if e["type"] != "Edit" or e["name"] != "index.html" else {**e, "value": "x\n" * 200} for e in els]
    box, _, how = locate_in(STEP[4], long, editor_from(long))         # scrolled somewhere unknown
    assert box is None and how.startswith("click into the editor")


def test_line_box_clamps_into_viewport():
    ed = Editor(file="a", text="", caret_line=50, caret_top=700, line_h=30, left=100, right=900, top=100, bottom=800)
    assert ed.line_box(1).y == 100 - 2           # scrolled above: top edge
    assert ed.line_box(99).y == 800 - 30 - 2     # scrolled below: bottom edge


def test_new_file_estimated_then_exact():
    box, exact = new_file_box(_els())
    assert not exact and box.w == round(51 * 0.79) and box.x + 4 * box.w + 4 == 94 + 523
    box, exact = new_file_box(_els(more=[{"type": "Button", "name": "New File...", "rect": [450, 216, 41, 40]}]))
    assert exact and box.x == 450


def test_locate_rules_per_step():
    els, ed = _els(), editor_from(_els())
    box, _, how = locate_in(STEP[14], els, ed)                        # click index.html tab
    assert box.x == 634 and how == "editor tab"
    box, _, how = locate_in(STEP[16], els, ed)                        # styles.css tab
    assert box.x == 848
    box, _, how = locate_in(STEP[4], els, ed)                         # type inside <body>
    assert how == "editor line 8"
    box, _, how = locate_in(STEP[17], els, ed)                        # styles.css isn't the active editor
    assert box is None and "not the active editor" in how
    box, _, how = locate_in(STEP[7], els, ed)                         # right-click index.html → Open with Live Server
    assert how == "first chip 'index.html'" and box.y == 262
    menu = {"type": "MenuItem", "name": "Open with Live Server", "rect": [300, 400, 400, 40]}
    box, _, how = locate_in(STEP[7], els + [menu], ed)
    assert box.y == 400
    box, _, how = locate_in(STEP[2], els, ed)                         # filename box not open yet
    assert box is None
    box, _, how = locate_in(STEP[2], els + [{"type": "Edit", "name": "", "rect": [150, 300, 460, 38], "value": ""}], ed)
    assert box.x == 150 and how == "filename box"


def test_pitch_from_gutter_rows():
    # 20 lines 34.2 px apart (VS Code's 19 px at 180 %), digits ~14 px tall with a gap in the middle stroke
    ink = [0.0] * 700
    for k in range(20):
        top = 10 + k * 34.2
        for r in range(14):
            y = int(top + r)
            if y < 700 and r not in (6, 7):
                ink[y] += 5.0
    p = pitch_from_rows(ink, approx=35)                # the textarea says 35: too coarse by 0.8 px a line
    assert p is not None and abs(p - 34.2) < 0.05
    assert pitch_from_rows([0.0] * 400, approx=35) is None
    assert pitch_from_rows([1.0] * 50, approx=35) is None


class FakeLocator:
    def __init__(self):
        self.box = None
        self.last_how = "not found"
        self.calls = 0

    def locate(self, step):
        from engine.schema.messages import Box
        self.calls += 1
        return (Box(x=1, y=2, w=3, h=4) if self.box else None), None


def test_player_uses_locator_and_refresh_sends_only_changes():
    loc = FakeLocator()
    p = Player(Session(TUT), Pins(), scheme_override="dark", locator=loc)
    out = p.handle({"type": "hello"})
    assert out[1].box is None and "Not found (not found)" in out[1].card.dev_hint
    assert p.refresh() == []                     # nothing moved
    loc.box = True
    out = p.refresh()
    assert out and out[1].box.x == 1
    assert p.refresh() == []


def test_pin_beats_locator():
    loc = FakeLocator()
    loc.box = True
    p = Player(Session(TUT), Pins(steps={1: Pin(box=(9, 9, 9, 9))}), scheme_override="dark", locator=loc)
    out = p.handle({"type": "hello"})
    assert out[1].box.x == 9 and loc.calls == 0
    assert p.refresh() == []
