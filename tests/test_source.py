"""Source view: what a step opens, on a PC that has the source and on a fresh clone. No model calls anywhere."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote

import pytest

from engine.basefile.parse import parse_file
from engine.compile.adapters import SourceBlocked, SourceError
from engine.compile.adapters import web as web_adapter
from engine.compile.adapters.text import from_text
from engine.compile.adapters.video import clip_path
from engine.live import source as sv
from engine.live.player import Player
from engine.live.session import Session
from engine.live.windows import OVERLAY_TITLE, Win, ours, pick
from engine.schema import messages as m
from engine.schema.tutorial import Source, SourceInfo, Step, Target, Tutorial, TutorialMeta

VIDEO_URL = "https://www.youtube.com/watch?v=abc"
PAGE_URL = "https://example.com/guide"
READ = "# Part one\n\nDo the first thing.\n\n# Part two\n\nDo the second thing."


@pytest.fixture(autouse=True)
def store(tmp_path, monkeypatch):
    monkeypatch.setattr(sv, "STORE", tmp_path / "sources")
    return tmp_path


def _step(n=1, **source) -> Step:
    return Step(n=n, title=f"Step {n}", action="look", target=Target(label="x", kind="window"), check="ok", source=Source(**source))


def _tut(kind="web", url=PAGE_URL, hash_="h1", steps=None, **extra) -> Tutorial:
    meta = TutorialMeta(title="T", app="App", source=SourceInfo(type=kind, url=url, hash=hash_, **extra))
    return Tutorial(meta=meta, steps=steps or [_step(anchor="#part-two")])


# ---------- plain logic ----------
@pytest.mark.parametrize("t,offset,want", [
    ("01:39-01:44", 0, (97.5, 106.0)),        # a short step is still shown long enough, from just before it
    ("01:39-02:39", 88, (9.5, 72.0)),         # times are the original's, the file starts at 88 s
    ("00:01", 0, (0.0, 8.0)),                 # never before the start of the file
    ("1:00:00", 0, (3598.5, 3607.0)),
])
def test_clip_range(t, offset, want):
    assert sv.clip_range(t, offset) == want


def test_video_links_open_at_the_moment():
    assert sv.video_link(VIDEO_URL, 99.7) == VIDEO_URL + "&t=99s"
    assert sv.video_link(VIDEO_URL + "&t=5s", 99) == VIDEO_URL + "&t=99s"
    assert sv.video_link("https://youtu.be/abc", 7) == "https://youtu.be/abc?t=7s"
    assert sv.video_link("https://vimeo.com/1", 7) == "https://vimeo.com/1#t=7s"
    assert sv.video_link("https://other.example/v", 7) == "https://other.example/v"


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///c:/windows/x", "ms-settings:", "//no-scheme", "", None])
def test_only_web_links_leave_for_the_browser(url):
    assert sv.safe_link(url) is None and sv.video_link(url, 1) is None and sv.page_link(url, "#a-b") is None


def test_page_links_ask_for_the_section_where_they_can():
    assert sv.page_link(PAGE_URL, "#1-create-a-new-part") == PAGE_URL + "#:~:text=create%20a%20new%20part"
    assert sv.page_link(PAGE_URL, "#x", heading="12.2. Creating Virtual Environments") == PAGE_URL + "#:~:text=Creating%20Virtual%20Environments"
    assert sv.page_link(PAGE_URL, "#step-3") == PAGE_URL            # a made-up name means nothing on the page
    assert sv.page_link(PAGE_URL, None) == PAGE_URL


def test_anchors_match_exactly_or_by_number():
    anchors = ["#start", "#1-create", "#10-finish", "#3-draw"]
    assert sv.resolve_anchor("#3-draw", anchors) == "#3-draw"
    assert sv.resolve_anchor("#step-1", anchors) == "#1-create"     # not #10-finish
    assert sv.resolve_anchor("#step-10", anchors) == "#10-finish"
    assert sv.resolve_anchor("#step-7", anchors) is None and sv.resolve_anchor("#nope", anchors) is None and sv.resolve_anchor(None, anchors) is None


def test_card_label():
    assert sv.label(_tut("video", VIDEO_URL), _step(t="01:39-01:44")) == "▶ 01:39"
    assert sv.label(_tut(), _step(anchor="#x")) == "Source"


# ---------- a video ----------
def test_a_kept_clip_plays_at_the_step(tmp_path):
    clip = tmp_path / "my clip.mp4"
    clip.write_bytes(b"x")
    sv.remember_video(clip, 88.0, "h1", VIDEO_URL)
    v = sv.Sources(_tut("video", VIDEO_URL)).view(_step(t="01:39-01:44"), 5)
    assert v.kind == "video" and v.where == "01:39–01:44" and (v.start, v.end) == (9.5, 18.0)
    assert unquote(v.video).endswith("my clip.mp4") and v.video.startswith("file:///")
    assert v.link == VIDEO_URL + "&t=99s"


def test_a_hand_written_file_finds_the_clip_a_compile_downloaded():
    """Gold files have no hash, only the same link and segment."""
    clip = clip_path(VIDEO_URL, 88.0, 625.0, sv.STORE)
    assert clip.name == "video.mp4"
    tut = _tut("video", VIDEO_URL, "TBD", segment="01:28-10:25")
    assert sv.Sources(tut).view(_step(t="01:39"), 5).kind == "none"
    clip.parent.mkdir(parents=True)
    clip.write_bytes(b"x")
    v = sv.Sources(tut).view(_step(t="01:39"), 5)
    assert v.kind == "video" and v.start == 9.5


def test_fresh_clone_video_says_so_and_links_to_the_moment():
    v = sv.Sources(_tut("video", VIDEO_URL)).view(_step(t="01:39-01:44"), 5)
    assert v.kind == "none" and v.video is None and "isn't on this PC" in v.message
    assert v.link == VIDEO_URL + "&t=99s" and "01:39" in v.link_label and v.choose == "video"


def test_a_video_that_moved_is_treated_as_gone(tmp_path):
    clip = tmp_path / "c.mp4"
    clip.write_bytes(b"x")
    sv.remember_video(clip, 0.0, "h1")
    clip.unlink()
    assert sv.Sources(_tut("video", VIDEO_URL)).view(_step(t="00:10"), 5).kind == "none"


def test_a_local_video_with_no_link_offers_only_the_file():
    v = sv.Sources(_tut("video", None)).view(_step(t="00:10"), 5)
    assert v.kind == "none" and v.link is None and v.choose == "video"


def test_choosing_a_video_file(tmp_path):
    s = sv.Sources(_tut("video", VIDEO_URL))
    wrong = tmp_path / "notes.txt"
    wrong.write_text("x")
    assert s.choose(str(wrong), _step(t="00:10"), 5).kind == "none"
    good = tmp_path / "v.mp4"
    good.write_bytes(b"x")
    v = s.choose(str(good), _step(t="00:10"), 5)
    assert v.kind == "video" and v.start == 8.5
    assert sv.Sources(_tut("video", VIDEO_URL)).view(_step(t="00:10"), 5).kind == "video"    # and stays chosen


# ---------- text and web pages ----------
def test_a_kept_reading_opens_at_the_section():
    ev = from_text(READ, url=PAGE_URL)
    sv.remember_reading(ev)
    v = sv.Sources(_tut(hash_=ev.hash)).view(_step(anchor="#part-two"), 5)
    assert v.kind == "text" and v.anchor == "#part-two" and v.where == "Part two" and v.note is None
    assert [b.text for b in v.blocks] == ["Part one", "Do the first thing.", "Part two", "Do the second thing."]
    assert v.link == PAGE_URL + "#:~:text=Part%20two"


def test_found_by_link_when_the_hash_is_unknown_and_by_number_for_gold():
    sv.remember_reading(from_text("# 3. Draw\n\nDraw it.", url=PAGE_URL))
    v = sv.Sources(_tut(hash_="TBD")).view(_step(anchor="#step-3"), 5)
    assert v.kind == "text" and v.anchor == "#3-draw"


def test_no_matching_section_shows_the_whole_text_and_says_so():
    ev = from_text(READ, url=PAGE_URL)
    sv.remember_reading(ev)
    v = sv.Sources(_tut(hash_=ev.hash)).view(_step(anchor="#gone"), 5)
    assert v.kind == "text" and v.anchor is None and "no section" in v.note


def test_pictures_are_kept_with_the_reading(tmp_path):
    from engine.compile.timeline import Evidence, Item
    sv.remember_reading(Evidence("web", "pic", [Item("text", "a", anchor="#s"), Item("image", "alt", anchor="#s", image=b"jpeg")]))
    v = sv.Sources(_tut(hash_="pic")).view(_step(anchor="#s"), 5)
    assert v.blocks[1].image.startswith("file:///") and Path(unquote(v.blocks[1].image[8:])).read_bytes() == b"jpeg"


def test_a_page_not_held_is_tried_once_then_shown(monkeypatch):
    asked = []

    def fetch(url, timeout=30):
        asked.append((url, timeout))
        return "<html><body><article><h2>Part two</h2><p>" + "words " * 40 + "</p></article></body></html>"
    monkeypatch.setattr(web_adapter, "fetch_page", fetch)
    s = sv.Sources(_tut())
    v = s.view(_step(anchor="#part-two"), 5)
    assert v.kind == "loading" and s.to_fetch == PAGE_URL and v.link
    s.fetch(s.to_fetch)
    assert asked == [(PAGE_URL, sv.FETCH_TIMEOUT_S)]
    v = s.view(_step(anchor="#part-two"), 5)
    assert v.kind == "text" and v.anchor == "#part-two" and s.to_fetch is None
    # the words are kept: a later run asks nobody
    assert sv.Sources(_tut()).view(_step(anchor="#part-two"), 5).kind == "text" and len(asked) == 1


@pytest.mark.parametrize("error,says", [(SourceBlocked("no"), "doesn't allow automatic reading"), (SourceError("down"), "can't be reached")])
def test_a_site_that_refuses_gets_a_clear_message_and_no_second_try(monkeypatch, error, says):
    asked = []

    def fetch(url, timeout=30):
        asked.append(url)
        raise error
    monkeypatch.setattr(web_adapter, "fetch_page", fetch)
    s = sv.Sources(_tut())
    s.view(_step(anchor="#1-do-this"), 5)
    s.fetch(s.to_fetch)
    v = s.view(_step(n=2, anchor="#2-then-that"), 5)
    assert v.kind == "none" and says in v.message and "example.com" in v.message
    assert s.to_fetch is None and len(asked) == 1
    assert v.link == PAGE_URL + "#:~:text=then%20that" and v.choose == "page"


def test_a_page_asked_about_while_loading_is_not_asked_again():
    s = sv.Sources(_tut())
    s.view(_step(anchor="#a"), 5)
    assert s.to_fetch
    v = s.view(_step(n=2, anchor="#b"), 5)
    assert v.kind == "loading" and s.to_fetch is None


def test_pasted_text_from_another_pc_offers_a_copy():
    v = sv.Sources(_tut("text", None)).view(_step(anchor="#x"), 5)
    assert v.kind == "none" and v.link is None and v.choose == "page" and s_no_fetch(v)


def s_no_fetch(v) -> bool:
    return "isn't on this PC" in v.message


def test_choosing_a_saved_page_after_a_refusal(tmp_path):
    s = sv.Sources(_tut())
    s.refused = "no"
    page = tmp_path / "saved.html"
    page.write_text("<html><body><article><h2>Part two</h2><p>" + "words " * 40 + "</p></article></body></html>", encoding="utf-8")
    v = s.choose(str(page), _step(anchor="#part-two"), 5)
    assert v.kind == "text" and v.anchor == "#part-two"


def test_a_challenge_page_saved_by_mistake_is_explained(tmp_path):
    s = sv.Sources(_tut())
    s.refused = "no"
    page = tmp_path / "saved.html"
    page.write_text("<html><title>Just a moment...</title></html>", encoding="utf-8")
    v = s.choose(str(page), _step(anchor="#x"), 5)
    assert v.kind == "none" and "security check" in v.note


def test_a_broken_index_is_nothing_held():
    sv.STORE.mkdir(parents=True)
    (sv.STORE / "index.json").write_text("{not json", encoding="utf-8")
    assert sv.held("h1", PAGE_URL) is None


# ---------- nothing about this PC goes in the tutorial file ----------
def test_compiled_files_hold_no_local_paths():
    for f in Path("tutorials").rglob("*.md"):
        text = f.read_text(encoding="utf-8")
        assert "file:///" not in text and "\\Users\\" not in text, f


# ---------- through the player ----------
def _player(tut=None) -> Player:
    return Player(Session(tut or _tut(steps=[_step(1, anchor="#part-one"), _step(2, anchor="#part-two")])))


def test_player_opens_the_current_steps_source_and_follows():
    ev = from_text(READ, url=PAGE_URL)
    sv.remember_reading(ev)
    p = _player(_tut(hash_=ev.hash, steps=[_step(1, anchor="#part-one"), _step(2, anchor="#part-two")]))
    p.handle({"type": "hello"})
    [v] = p.handle({"type": "source"})
    assert isinstance(v, m.SourceView) and v.n == 1 and v.anchor == "#part-one" and not v.follow
    p.handle({"type": "next"})
    [v] = p.handle({"type": "source", "follow": True})
    assert v.n == 2 and v.anchor == "#part-two" and v.follow


def test_card_carries_the_source_button_and_finished_tutorials_still_answer():
    p = _player()
    out = p.handle({"type": "hello"})
    guide = next(x for x in out if isinstance(x, m.Guide))
    assert guide.card.source == "Source"
    p.handle({"type": "next"})
    p.handle({"type": "next"})
    assert p.session.finished
    assert p.handle({"type": "source"})[0].n == 2


def test_source_doesnt_move_the_step_or_call_a_model():
    p = _player()
    p.handle({"type": "hello"})
    p.handle({"type": "source"})
    assert p.session.current == 1 and p.session.statuses[0] == "pending"


def test_messages_on_the_wire():
    v = m.SourceView(kind="text", n=1, of=2, title="t", tutorial="T", blocks=[m.SourceBlock(kind="text", text="a")])
    assert json.loads(m.dumps(v))["blocks"] == [{"kind": "text", "text": "a"}]
    assert m.parse_from_overlay({"type": "source_file", "path": "x"}).path == "x"
    assert m.parse_from_overlay({"type": "source"}).follow is False


# ---------- the source window never passes for the app ----------
def test_our_windows_arent_the_app():
    src = Win(1, "GhostGuide: source", (0, 0, 500, 500))
    app = Win(2, "index.html - Visual Studio Code", (0, 0, 500, 500))
    assert ours("GhostGuide: source", "source") and not ours("GhostGuide: source", "GhostGuide: source")
    assert pick([src, app], "source") is None
    assert pick([src, app], "Visual Studio Code") is app
    assert pick([src], "GhostGuide: source") is src       # the checks can still find it by its whole name
    assert pick([Win(3, OVERLAY_TITLE, (0, 0, 9, 9)), src], "GhostGuide overlay") is None


def test_gold_and_compiled_files_all_get_a_view():
    """Every step of the files we ship has somewhere to go, on a PC with nothing."""
    for f in list(Path("tutorials").glob("*.md")) + list(Path("tutorials/compiled").glob("*.md")):
        tut = parse_file(f)
        s = sv.Sources(tut)
        for step in tut.steps:
            v = s.view(step, len(tut.steps))
            assert v.kind in ("none", "loading") and v.link, (f, step.n)
            assert sv.label(tut, step)
