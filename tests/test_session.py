import json

from engine.basefile.parse import parse_file
from engine import config
from engine.live.session import Session, _ranges

TUT = config.TUTORIALS / "youtube-clone-vscode.md"


def make(tmp_path=None, checker=None):
    return Session(parse_file(TUT), save_path=(tmp_path / "s.json") if tmp_path else None, checker=checker)


def test_next_back_skip_jump():
    s = make()
    assert s.current == 1 and s.of == 23
    s.next()
    assert s.current == 2 and s.status(1) == "done"
    ev = s.skip()
    assert ev.kind == "skipped" and s.status(2) == "skipped" and s.current == 3
    s.back()
    assert s.current == 2 and s.status(2) == "skipped"      # going back doesn't un-skip
    assert s.back().kind == "moved" and s.back().kind == "noop"
    s.jump(23)
    ev = s.next()
    assert ev.kind == "finished" and "1 skipped" in ev.text and s.finished and s.step is None
    assert s.next().kind == "noop" and s.skip().kind == "noop"


def test_skip_never_counts_as_done():
    s = make()
    for _ in range(23):
        s.skip()
    assert s.finished and set(s.statuses) == {"skipped"}


def test_hide_resume_catch_up_stops_at_first_not_done():
    done_upto = 5
    s = make(checker=lambda step: "done" if step.n <= done_upto else "not_yet")
    s.next()                                  # step 1 by hand
    assert s.hide().kind == "hidden" and s.hidden and s.hide().kind == "noop"
    ev = s.resume()
    assert not s.hidden and ev.kind == "caught_up" and ev.steps == [2, 3, 4, 5]
    assert s.current == 6 and s.statuses[:5] == ["done"] * 5
    assert "2–5" in ev.text


def test_resume_without_checker_or_unknown_stays():
    s = make(checker=lambda step: "unknown")
    s.hide()
    assert s.resume().kind == "resumed" and s.current == 1
    s2 = make()
    s2.hide()
    assert s2.resume().kind == "resumed" and s2.current == 1


def test_progress_saved_and_restored(tmp_path):
    s = make(tmp_path)
    s.next(); s.skip(); s.next()
    data = json.loads((tmp_path / "s.json").read_text())
    assert data["current"] == 4 and data["statuses"][:3] == ["done", "skipped", "done"]
    s2 = make(tmp_path)
    assert s2.restore() and s2.current == 4 and s2.status(2) == "skipped"


def test_restore_refuses_other_tutorial(tmp_path):
    (tmp_path / "s.json").write_text(json.dumps({"tutorial": "other", "of": 23, "current": 9, "statuses": ["done"] * 23}))
    s = make(tmp_path)
    assert not s.restore() and s.current == 1


def test_ranges():
    assert _ranges([3, 4, 5, 8]) == "3–5, 8" and _ranges([1]) == "1" and _ranges([]) == ""
