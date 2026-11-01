"""From the first manual runs: Do it for me that doesn't look like it failed, pictures in the source view, a way to end, the next
step's outline ready as it comes up."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from engine.basefile.parse import parse_file
from engine.compile.adapters.web import from_html, web_address
from engine.live import execute, source
from engine.live.locate.boxcheck import BoxCheck
from engine.live.locate.menu import Hops
from engine.live.locate.resolver import Resolver
from engine.live.player import Player
from engine.live.session import Session
from engine.schema import messages as m
from engine.schema.messages import Box

MUG = parse_file("tutorials/mug-solidworks.md")
BOX = Box(x=40, y=40, w=20, h=20)
CLICK = MUG.step(11)      # a button, no shortcut
TEXT = "<p>" + "Words about the step. " * 12 + "</p>"


def hop_step():
    s = MUG.step(5).model_copy(deep=True)
    s.target.shortcut = None
    return s


# ---------- Do it for me
def test_a_box_something_vouched_for_runs_on_the_first_press():
    assert execute.needs_confirm(CLICK, "vision", BOX)
    assert not execute.needs_confirm(CLICK, "vision", BOX, vouched=True)


def test_a_key_that_deletes_always_asks():
    s = MUG.step(22).model_copy(deep=True, update={"params": {"keys": ["Delete"]}})
    assert execute.needs_confirm(s, "uia", None, vouched=True)


def test_a_route_without_a_shortcut_can_click_the_hop_it_is_on():
    s = hop_step()
    assert not execute.can_do(s, None) and execute.can_do(s, BOX)
    assert execute.plan(s, BOX)[0].at == BOX.center
    assert execute.plan(s, BOX, (99, 98))[0].at == (99, 98)     # a chip's small dropdown arrow
    assert execute.needs_confirm(s, "vision", BOX)


class Ran:
    def __init__(self):
        self.ops = []

    def run(self, ops):
        self.ops += ops


def player(tmp_path, locator=None, tut=MUG, n=11):
    s = Session(tut, save_path=tmp_path / "s.json")
    s.current = n
    p = Player(s, locator=locator or SimpleNamespace(locate=lambda st: (BOX, None), last_how="", last_extra={}, last_stage="vision"), start_items=None)
    p.executor = Ran()
    p.apply_located((n, BOX, None, {}))
    return p


def test_the_second_press_shows_on_the_button_and_the_second_press_runs(tmp_path):
    p = player(tmp_path)
    out = p.handle('{"type": "do_it"}')
    guide = next(x for x in out if isinstance(x, m.Guide))
    assert guide.card.confirm and not p.executor.ops
    p.handle('{"type": "do_it"}')
    assert [o.kind for o in p.executor.ops] == ["click"]


def test_a_vouched_box_runs_at_once(tmp_path):
    loc = SimpleNamespace(locate=lambda st: (BOX, None), last_how="", last_extra={}, last_stage="vision", vouched=lambda b: True)
    p = player(tmp_path, loc)
    p.handle('{"type": "do_it"}')
    assert [o.kind for o in p.executor.ops] == ["click"]


def test_what_vouches_for_a_box():
    r = Resolver(SimpleNamespace(window="W", last_how="", last_extra={}), None, None, None, None, Hops())
    assert not r.vouched(BOX)
    r._tip_ok.add(("New", 40, 40, 20, 20))
    assert r.vouched(BOX) and not r.vouched(Box(x=1, y=1, w=2, h=2))
    r = Resolver(SimpleNamespace(window="W", last_how="", last_extra={}), None, None, None, None, Hops(), looks=lambda b, l: True)
    r.last_stage = "appmap"
    assert r.vouched(BOX)


def test_a_models_yes_vouches_only_for_that_box():
    c = BoxCheck("A", [lambda step, png, text, tag: SimpleNamespace(result="done", why="")], lambda: None, start=lambda run: run())
    from PIL import Image
    c.grab = lambda: (Image.new("RGB", (300, 300)), (0, 0), 1.0)
    c.say(CLICK, "Offset", BOX)
    assert c.agrees(BOX) and not c.agrees(Box(x=1, y=1, w=2, h=2))


# ---------- the source view's pictures
SAVED = ('<article>' + TEXT + '<img src="./page_files/fig-1024x550.png" width="660" height="354" '
         'srcset="https://site.example/fig-300x161.png 300w, https://site.example/fig-1024x550.png 1024w">' + TEXT + '</article>')


def test_the_largest_web_address_wins_and_small_pictures_dont_count():
    a = {"src": "./x.png", "srcset": "https://s.example/a.png 300w, https://s.example/b.png 1024w, http://s.example/c.png 2000w"}
    assert web_address(a, 64) == "https://s.example/b.png"
    assert web_address({"src": "https://s.example/a.png"}, 64) == "https://s.example/a.png"
    assert web_address({"src": "./a.png"}, 64) is None
    assert web_address({"src": "https://s.example/logo.png", "width": "30"}, 64) is None


def test_a_saved_page_missing_its_picture_keeps_where_it_lives_for_the_source_view(tmp_path, monkeypatch):
    monkeypatch.setattr(source, "STORE", tmp_path)
    ev = from_html(SAVED, None, lambda src: None, web_images=True)
    source.remember_reading(ev, "h")
    blocks = source._reading(source.held("h", None))
    assert [b["web_image"] for b in blocks if b["kind"] == "image"] == ["https://site.example/fig-1024x550.png"]
    assert m.SourceBlock(**blocks[1]).web_image


def test_a_compile_never_gets_a_picture_from_the_web():
    ev = from_html(SAVED, None, lambda src: None)
    assert not [i for i in ev.items if i.kind == "image"]


def test_a_cached_address_that_isnt_https_is_dropped(tmp_path, monkeypatch):
    monkeypatch.setattr(source, "STORE", tmp_path)
    folder = tmp_path / "readings" / "h"
    folder.mkdir(parents=True)
    (folder / "reading.json").write_text(json.dumps([{"kind": "image", "text": "", "web_image": "file:///c:/secret.png"}]), encoding="utf-8")
    assert "web_image" not in source._reading({"reading": "h"})[0]


# ---------- the next step's outline
def test_the_next_steps_target_is_ready_and_a_miss_clears_it(tmp_path):
    seen = {"at": (BOX, None, {"x": 1})}
    loc = SimpleNamespace(locate=lambda st: (BOX, None), last_how="", last_extra={}, peek=lambda st: seen["at"])
    p = player(tmp_path, loc)
    p.locate_current()
    assert p._located[12] == (BOX, None) and p._located_extra[12] == {"x": 1}
    seen["at"] = None
    p.locate_current()
    assert 12 not in p._located


def test_a_peek_that_fails_changes_nothing(tmp_path):
    def peek(st):
        raise RuntimeError("window closing")
    loc = SimpleNamespace(locate=lambda st: (BOX, None), last_how="", last_extra={}, peek=peek)
    assert player(tmp_path, loc).locate_current()[0] == 11


def test_the_vscode_finder_peeks_without_reading_again(monkeypatch):
    from engine.live.locate import vscode
    loc = vscode.VSCodeLocator("Visual Studio Code")
    assert loc.peek(CLICK) is None      # nothing read yet
    monkeypatch.setattr(vscode, "locate_in", lambda step, els, ed: (BOX, None, "named control"))
    monkeypatch.setattr(vscode, "editor_from", lambda els: None)
    monkeypatch.setattr(vscode, "dump", lambda w: pytest.fail("a peek reads nothing"))
    loc.last_els = [{"type": "Button"}]
    assert loc.peek(CLICK) == (BOX, None, {})


# ---------- End
def test_end_stops_the_engine(tmp_path):
    from websockets.asyncio.client import connect

    from engine.server import serve

    p = player(tmp_path)

    async def run():
        server = asyncio.create_task(serve(p, port=8799, log=lambda s: None))
        await asyncio.sleep(0.2)
        async with connect("ws://127.0.0.1:8799") as ws:
            await ws.send('{"type": "end"}')
        await asyncio.wait_for(server, 5)
    asyncio.run(run())


def test_end_is_a_message_on_both_sides():
    assert "end" in m.FROM_OVERLAY_TYPES
    assert m.parse_from_overlay('{"type": "end"}').type == "end"


# ---------- the second run's comments
def test_snug_moves_a_box_half_off_a_control_onto_it():
    from PIL import Image, ImageDraw

    from engine.live.capture import snug
    img = Image.new("RGB", (300, 200), (225, 225, 225))
    d = ImageDraw.Draw(img)
    d.rectangle((100, 40, 124, 68), fill=(40, 40, 40))         # the icon
    d.rectangle((150, 40, 174, 68), fill=(40, 40, 40))         # its neighbour
    d.line((0, 90, 299, 90), fill=(90, 90, 90))                # a line across the window
    assert snug(img, (98, 52, 26, 36), pad=2) == (98, 38, 29, 33)
    assert snug(Image.new("RGB", (200, 200)), (50, 45, 60, 70)) == (50, 45, 60, 70)     # nothing there
    assert snug(img, (40, 84, 20, 12)) == (40, 84, 20, 12)                               # only the line


def test_after_do_it_a_step_that_hasnt_checked_done_is_said(tmp_path, monkeypatch):
    from engine.live import player as pl
    p = player(tmp_path)
    p._did_it = (11, 0.0)
    monkeypatch.setattr(pl.time, "monotonic", lambda: 1.0)
    assert p._didnt_take() == []
    monkeypatch.setattr(pl.time, "monotonic", lambda: pl.DID_IT_WAIT_S + 1)
    assert "hasn't checked done" in p._didnt_take()[0].text
    assert p._didnt_take() == []       # once


def test_next_past_a_rule_that_says_not_yet_is_said(tmp_path):
    from engine.live.verify import Verdict
    p = player(tmp_path)
    p.tracker = SimpleNamespace(cached=lambda s: Verdict("not_yet", "rule", why="no Sketch2"), forget=lambda n: None)
    assert "no Sketch2" in p._not_seen_yet()[0].text
    p.tracker = SimpleNamespace(cached=lambda s: Verdict("not_yet", "diff", why="nothing changed yet"), forget=lambda n: None)
    assert p._not_seen_yet() == []


def test_a_shortcut_alone_doesnt_stop_a_box_being_remembered(tmp_path):
    from engine.appmap.store import AppMapStore
    store = SimpleNamespace(learn=lambda *a: True)
    r = Resolver(SimpleNamespace(window="W", last_how="", last_extra={}), store, lambda w: (0, 0, 500, 500), None, None, Hops())
    step = MUG.step(1)
    r.last_extra = {"route": {"shortcut": "Ctrl+N"}}
    assert r.learn(step, BOX)
    r.last_extra = {"route": {"path": ["File", "New"]}}
    assert not r.learn(step, BOX)


def test_a_route_that_dead_ended_offers_the_apps_own_search(monkeypatch):
    from engine.live.locate import menu
    monkeypatch.setattr(menu, "search_hint", lambda store, label: f"search for {label}")
    r = Resolver(SimpleNamespace(window="W", last_how="", last_extra={}, follows_hops=True, locate=lambda s, l=None: (None, None)), None, None, None, None, Hops())
    s = MUG.step(29)
    r._gave_up.add(s.n)
    r.locate(s)
    assert r.last_extra["search"] == "search for Plane"
    r.forget(s.n)
    assert s.n not in r._gave_up


# ---------- a page saved as one file
def _single_file(path, html, pictures):
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["Subject"] = "saved"
    msg.make_mixed()
    page = EmailMessage()
    page.set_content(html, subtype="html")
    page["Content-Location"] = "https://site.example/article"
    msg.attach(page)
    for where, data in pictures.items():
        pic = EmailMessage()
        pic.set_content(data, maintype="image", subtype="png")
        pic["Content-Location"] = where
        msg.attach(pic)
    path.write_bytes(msg.as_bytes())


def _png():
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.effect_noise((400, 300), 60).convert("RGB").save(buf, "PNG")
    return buf.getvalue()


PAGE = ("<article><h2>Make the part</h2>" + TEXT + '<img src="https://site.example/a-1024.png" '
        'srcset="https://site.example/a-1024.png 1024w, https://site.example/a-300.png 300w" width="660" height="354">' + TEXT + "</article>")


def test_a_single_file_page_gives_its_own_pictures(tmp_path):
    from engine.compile.adapters.web import from_file
    f = tmp_path / "page.mhtml"
    _single_file(f, PAGE, {"https://site.example/a-1024.png": _png()})
    pics = [i for i in from_file(f).items if i.kind == "image"]
    assert len(pics) == 1 and pics[0].image


def test_it_takes_whichever_size_the_browser_kept(tmp_path):
    from engine.compile.adapters.web import from_file
    f = tmp_path / "page.mhtml"
    _single_file(f, PAGE, {"https://site.example/a-300.png": _png()})
    assert [i for i in from_file(f).items if i.kind == "image"][0].image


def test_a_single_file_page_never_fetches(tmp_path, monkeypatch):
    from engine.compile.adapters import web
    monkeypatch.setattr(web, "fetch_limited", lambda *a, **k: pytest.fail("fetched"))
    f = tmp_path / "page.mhtml"
    _single_file(f, PAGE, {})
    assert not [i for i in web.from_file(f).items if i.kind == "image" and i.image]


def test_a_file_that_holds_no_page_says_what_to_save(tmp_path):
    from engine.compile.adapters import SourceError
    from engine.compile.adapters.web import from_file
    f = tmp_path / "page.mhtml"
    f.write_text("not a saved page", encoding="utf-8")
    with pytest.raises(SourceError, match="Single File"):
        from_file(f)


def test_a_saved_challenge_page_is_explained(tmp_path):
    from engine.compile.adapters import SourceBlocked
    from engine.compile.adapters.web import from_file
    f = tmp_path / "saved.html"
    f.write_text("<html><title>Just a moment...</title></html>", encoding="utf-8")
    with pytest.raises(SourceBlocked, match="security check"):
        from_file(f)


def test_a_compile_of_a_single_file_page_is_read_as_a_web_page():
    from engine.compile.pipeline import WEB_FILES
    assert ".mhtml" in WEB_FILES and ".mht" in WEB_FILES


def test_a_saved_page_that_lost_pictures_says_so_and_how_to_keep_them(tmp_path, monkeypatch):
    from engine.compile import pipeline
    monkeypatch.setattr(source, "STORE", tmp_path / "s")
    page = tmp_path / "saved.html"
    page.write_text(SAVED, encoding="utf-8")
    ev = pipeline.web.from_file(page)
    said = pipeline._keep_for_source_view(str(page), pipeline.Options(), ev)
    assert "0 of its 1 pictures" in said[0] and "Single File" in said[0]


def test_a_single_file_page_with_all_its_pictures_says_nothing(tmp_path, monkeypatch):
    from engine.compile import pipeline
    monkeypatch.setattr(source, "STORE", tmp_path / "s")
    f = tmp_path / "page.mhtml"
    _single_file(f, PAGE, {"https://site.example/a-1024.png": _png()})
    assert pipeline._keep_for_source_view(str(f), pipeline.Options(), pipeline.web.from_file(f)) == []


# ---------- from the Roblox run
def _drag(where):
    s = MUG.step(6).model_copy(deep=True)
    s.action, s.target.where, s.params = "drag", where, {"direction": "in whatever direction you want"}
    return s


def test_a_drag_says_what_to_hold():
    from engine.live.plan import _detail
    assert _detail(_drag("3D viewport, while holding right-click"), "ghost_line") == "Drag in whatever direction you want while holding right-click."
    assert _detail(_drag("3D viewport"), "ghost_line") == "Drag in whatever direction you want."


def _keys(*keys):
    return MUG.step(22).model_copy(deep=True, update={"params": {"keys": list(keys)}})


def test_separate_keys_arent_pressed_as_one_chord():
    assert execute.unsafe(_keys("W", "A", "S", "D")) and not execute.can_do(_keys("W", "A", "S", "D"), None)
    assert execute.can_do(_keys("F"), None) and execute.can_do(_keys("Ctrl", "S"), None)


def test_a_shortcut_named_as_a_window_may_be_checked_by_a_model():
    from engine.live.verify import Tracker
    s = MUG.step(22).model_copy(deep=True)
    s.target.kind, s.target.label = "window", "WASD"
    t = Tracker(SimpleNamespace(steps=[s]), "Roblox Studio", None, lambda w: [])
    assert t._kept_here(s) is None
    watched = s.model_copy(deep=True, update={"action": "wait"})
    assert t._kept_here(watched) == "it isn't the tutorial's app"
