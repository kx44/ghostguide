"""A tutorial's name for an app needn't be in the window's title: any program can be the app (live/windows.py)."""
import json

from engine.live.player import Player
from engine.live.session import Session
from engine.live.windows import Program, Win, bound_to, pick, program_is, use_front
from engine.schema.messages import parse_from_overlay
from engine.schema.tutorial import Source, Step, Target, Tutorial, TutorialMeta, SourceInfo


def win(hwnd, title, minimized=False):
    return Win(hwnd, title, (0, 0, 800, 600), minimized)


PROGRAMS = {1: Program("winword", "Microsoft Word"), 2: Program("excel", "Microsoft Excel"),
            3: Program("powerpnt", "Microsoft PowerPoint"), 4: Program("acad", "AutoCAD Application"),
            5: Program("powershell", "Windows PowerShell"), 6: Program("chrome", "Google Chrome"),
            7: Program("code", "Visual Studio Code"), 8: Program("mystery", "")}
WINS = [win(7, "notes - Visual Studio Code"), win(1, "Document1 - Word"), win(2, "Book1"), win(3, "Deck"),
        win(4, "Drawing1.dwg"), win(5, "C:\\Users\\me\\project"), win(6, "Inbox - Google Chrome"), win(8, "untitled")]


def of(w):
    return PROGRAMS[w.hwnd]


def test_the_name_is_found_by_program_when_the_title_doesnt_say():
    for label, hwnd in [("Microsoft Word", 1), ("Word", 1), ("Microsoft Excel", 2), ("Excel", 2), ("MS Excel", 2),
                        ("PowerPoint", 3), ("AutoCAD", 4)]:
        assert pick(WINS, label, of).hwnd == hwnd, label


def test_a_terminal_is_found_whatever_its_title_says():
    for label in ("Terminal", "PowerShell", "Windows Terminal", "Command Prompt"):
        assert pick(WINS, label, of).hwnd == 5, label


def test_a_title_about_the_app_doesnt_beat_a_terminal_or_browser_program():
    wins = [win(7, "terminal-notes - Visual Studio Code"), win(5, "build")]
    assert pick(wins, "Terminal", of).hwnd == 5


def test_a_name_nothing_goes_by_isnt_guessed():
    assert pick(WINS, "Blender", of) is None
    assert pick(WINS, "Microsoft", of) is None            # says nothing about which app
    assert not program_is("Go", Program("gogh", "Gogh paint"))     # a short name must be a whole word
    assert not program_is("Word Counter", Program("winword", "Microsoft Word"))    # every word of the name


def test_a_program_you_chose_comes_first_and_a_gone_one_falls_back():
    assert pick(WINS, "Anything At All", of, bound="mystery").hwnd == 8
    assert pick(WINS, "Word", of, bound="mystery").hwnd == 8
    assert pick(WINS, "Word", of, bound="closed-now").hwnd == 1


def test_ours_minimised_and_browser_tabs_never_count_by_program():
    wins = [win(1, "x", minimized=True), win(9, "GhostGuide engine")]
    assert pick(wins, "Word", of) is None
    assert pick([win(6, "How to use Word - Google Chrome")], "Word", of) is None


def test_titles_alone_still_work():
    assert pick([win(1, "Mug - SOLIDWORKS")], "SOLIDWORKS").hwnd == 1


def test_use_front_remembers_the_program_and_refuses_ours(tmp_path, monkeypatch):
    from engine.live import windows
    monkeypatch.setenv("GG_LOCAL_APPMAPS", str(tmp_path))
    monkeypatch.setattr(windows, "program", lambda hwnd: Program("mystery", "Mystery Tool"))
    monkeypatch.setattr(windows, "foreground", lambda: win(8, "untitled"))
    assert use_front("Some App") == "Mystery Tool"
    assert bound_to("some app") == "mystery"
    assert json.loads((tmp_path / windows.BINDINGS_FILE).read_text(encoding="utf-8")) == {"some app": "mystery"}
    for title in ("GhostGuide engine", windows.OVERLAY_TITLE, ""):
        monkeypatch.setattr(windows, "foreground", lambda t=title: win(8, t))
        assert use_front("Other") is None
    assert bound_to("other") is None


def _player():
    step = Step(n=1, title="One", action="look", target=Target(label="x", kind="canvas"), check="seen", source=Source(anchor="#a"))
    tut = Tutorial(meta=TutorialMeta(title="T", app="Some App", source=SourceInfo(type="text")), steps=[step])
    return Player(Session(tut), start_items=lambda: [])


def test_use_window_message_says_what_happened():
    assert parse_from_overlay({"type": "use_window"}).type == "use_window"
    p = _player()
    p.window_name = "Some App"
    p.use_window = lambda app: None
    assert "first" in p.handle({"type": "use_window"})[-1].text
    p.use_window = lambda app: "Mystery Tool"
    assert p.handle({"type": "use_window"})[-1].text == "Using Mystery Tool as Some App."
