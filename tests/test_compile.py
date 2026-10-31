"""The compiler without a network: adapters, timeline, passes, enrich, cache and the rules about what shipped code may touch."""
import io
import json
import re
import wave
from pathlib import Path

import pytest

from engine.appmap.store import AppMapStore
from engine.basefile.parse import parse_file
from engine.compile import timeline as tl
from engine.compile.adapters import SourceBlocked, SourceError, text as text_adapter, video, web
from engine.compile.enrich import enrich, new_controls
from engine.compile.passes import CompileError, prompts_version, read_json
from engine.compile.passes.merge import merge, to_tutorial
from engine.compile.pipeline import Options, compile_tutorial
from engine.compile.timeline import Evidence, Item, Segment
from engine.models.client import ModelClient
from engine.schema.tutorial import Tutorial, TutorialMeta

ROOT = Path(__file__).resolve().parent.parent
PAGE = """<!doctype html><html><head><title>Build a box</title><meta name="author" content="A. Writer">
<meta property="article:published_time" content="2019-05-01T00:00:00"><link rel="canonical" href="https://example.com/box"></head>
<body><nav><p>Home About Contact and many other links nobody wants in a tutorial at all</p></nav>
<div class="wrap"><aside><p>Sign up for the newsletter</p></aside>
<article><h1>Build a box</h1><p>First open the app and click New to start a fresh document for the box.</p>
<img src="big.png" alt="the new button"><img src="tiny.png" alt="icon">
<h2 id="lid">Add a lid</h2><p>Now choose Lid from the menu and set the height you want for it.</p>
<ul><li>Press Save.</li></ul><pre>x = 1
y = 2</pre><script>alert(1)</script></article></div>
<footer><p>Copyright notice</p></footer></body></html>"""


def _png(w, h):
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(b, "PNG")
    return b.getvalue()


IMAGES = {"big.png": _png(800, 400), "tiny.png": _png(32, 32)}


def _reply(text, usage=(100, 50)):
    return {"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": usage[0], "completion_tokens": usage[1]}}


RAW = json.dumps({"setup": ["App open"], "actions": [
    {"action": "click", "label": "New", "kind": "button", "at": "#start", "evidence": "said"}]})
STEP = {"title": "Click New", "action": "click", "target": {"label": "New", "kind": "button", "where": "toolbar"},
        "check": "A document opens", "source": {"anchor": "#start"}, "confidence": "high", "params": {}, "why": ""}
DRAFT = json.dumps({"title": "Build a box", "app": "BoxCAD", "start_state": "App open", "steps": [STEP]})


class Fake:
    """Answers pass 1, pass 2 and enrich like the API, and counts them."""

    def __init__(self, draft=DRAFT, answer='[]'):
        self.draft, self.answer, self.calls = draft, answer, []

    def __call__(self, request):
        if "input" in request:
            self.calls.append("enrich")
            return {"output": [{"type": "web_search_call"}, {"type": "message", "content": [
                {"type": "output_text", "text": self.answer, "annotations": [{"type": "url_citation", "url": "https://help.example.com/a"}]}]}],
                "usage": {"input_tokens": 10, "output_tokens": 5}}
        name = request["response_format"]["json_schema"]["name"]
        self.calls.append(name)
        return _reply(RAW if name == "raw_actions" else self.draft)


def _client(tmp_path, fake, mode="record", budget=5.0):
    return ModelClient(mode=mode, budget_usd=budget, cassette_dir=tmp_path / "cass", cost_log=tmp_path / "costs.jsonl", transport=fake)


# ---- web adapter ----
def test_web_keeps_the_main_text_and_images_in_place():
    ev = web.from_html(PAGE, None, lambda src: IMAGES.get(src))
    kinds = [i.kind for i in ev.items]
    text = " ".join(i.text for i in ev.items)
    assert "newsletter" not in text and "Copyright" not in text and "alert" not in text and "Home About" not in text
    assert kinds.count("image") == 1 and ev.items[kinds.index("image")].text == "the new button"     # the icon is dropped
    assert kinds.index("image") < [i.text for i in ev.items].index("Add a lid")
    assert ev.url == "https://example.com/box" and ev.author == "A. Writer" and ev.published == "2019-05-01"
    assert next(i for i in ev.items if i.text == "Add a lid").anchor == "#lid"
    assert "x = 1\ny = 2" in text


def test_web_hash_changes_with_content_only():
    a = web.from_html(PAGE, None, lambda s: IMAGES.get(s))
    b = web.from_html(PAGE, "https://example.com/box", lambda s: IMAGES.get(s))
    c = web.from_html(PAGE.replace("fresh", "new"), None, lambda s: IMAGES.get(s))
    assert a.hash == b.hash != c.hash


@pytest.mark.parametrize("status,body", [(403, "<p>no</p>"), (429, ""), (503, ""), (200, "<title>Just a moment...</title>"),
                                         (200, "Performing security verification")])
def test_a_refusing_site_is_reported_and_not_retried(monkeypatch, status, body):
    import httpx
    calls = []

    def fake_get(url, headers, **kw):
        calls.append(headers["User-Agent"])
        return httpx.Response(status, text=body, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    with pytest.raises(SourceBlocked, match="save it"):
        web.fetch_page("https://example.com/a")
    assert calls == [web.USER_AGENT]              # one try, as ourselves
    assert "GhostGuide" in web.USER_AGENT and "Mozilla" not in web.USER_AGENT


def test_a_saved_security_check_page_is_refused():
    with pytest.raises(SourceBlocked, match="save it again"):
        web.from_html("<title>Just a moment...</title><p>Performing security verification</p>", None, lambda s: None)


def test_a_saved_page_never_goes_to_the_network(tmp_path):
    (tmp_path / "p_files").mkdir()
    (tmp_path / "p_files" / "a.png").write_bytes(IMAGES["big.png"])
    page = tmp_path / "p.html"
    page.write_text('<article><p>' + "words " * 20 + '</p><img src="./p_files/a.png"><img src="https://evil.example/x.png"><img src="./p_files/gone.png"></article>', encoding="utf-8")
    assert web.from_file(page).images == 1


def test_a_page_without_text_says_so():
    with pytest.raises(SourceError):
        web.from_html("<html><body><img src='a.png'></body></html>", None, lambda s: None)


# ---- text adapter ----
def test_text_headings_become_anchors():
    ev = text_adapter.from_text("# Part one\nDo this.\n\nThen that.\n\n# Part two\n\nMore.")
    assert [i.kind for i in ev.items] == ["heading", "text", "text", "heading", "text"]
    assert ev.items[2].anchor == "#part-one" and ev.items[4].anchor == "#part-two"
    with pytest.raises(SourceError):
        text_adapter.from_text("  \n ")


# ---- video adapter, pure parts ----
def test_captions_drop_rolling_repeats():
    vtt = """WEBVTT

00:01:40.000 --> 00:01:42.000
<c>hello</c> there

00:01:42.000 --> 00:01:44.000
hello there
and now

00:01:44.000 --> 00:01:46.000
and now
"""
    assert [(t["t"], t["text"]) for t in video.parse_vtt(vtt)] == [(100.0, "hello there"), (102.0, "and now")]


def test_keyframes_wait_for_rest_and_ignore_a_still_screen():
    changes = [0.0] * 200
    changes[10] = 0.05                    # a click at 10 s, settled at once
    settled = [True] * 200
    kept = video.pick_keyframes(changes, settled, 0.002)
    assert 10 in kept and len(kept) <= 5  # a still screen only gets the odd frame
    typing = [0.001] * 30
    busy = video.pick_keyframes(typing, [False] * 30, 0.002)
    assert busy == [0, 6, 12, 18, 24]     # never at rest: every few seconds


def test_keyframes_ignore_a_webcam_and_fit_the_limit():
    np = pytest.importorskip("numpy")
    rng = np.random.default_rng(1)
    frames = np.zeros((120, 60, 80), dtype=np.uint8)
    frames[:, 40:, 60:] = rng.integers(0, 255, (120, 20, 20), dtype=np.uint8)    # webcam corner, always moving
    frames[50:, :10, :10] = 200                                                   # one real change
    t = video.keyframe_times(frames, 150)
    assert 51 in t or 50 in t
    assert len(t) < 10                    # the webcam alone doesn't make frames
    frames[:, :30, :30] = rng.integers(0, 255, (120, 30, 30), dtype=np.uint8) // 2 * (np.arange(120) % 7 < 3)[:, None, None]
    assert len(video.keyframe_times(frames, 12)) <= 12


def test_times():
    assert video.seconds("01:28") == 88 and video.seconds("1:00:01") == 3601 and video.seconds(None) is None


# ---- timeline ----
def _narr(t):
    return Item("narration", f"line {t}", t=float(t), end=t + 1.0)


def test_video_cuts_at_a_narration_turn_under_the_image_limit():
    items = sorted([_narr(t) for t in range(0, 400, 7)] + [Item("image", t=float(t), image=b"j") for t in range(0, 400, 2)],
                   key=lambda i: i.t)
    parts = tl.cut_video(items)
    assert len(parts) > 2
    for p in parts:
        assert sum(i.kind == "image" for i in p) <= tl.HARD_MAX_IMAGES
    assert all(p[0].kind == "narration" for p in parts[1:])


def test_images_alone_are_still_cut_below_the_api_limit():
    items = [Item("image", t=float(t), image=b"j") for t in range(200)]
    assert all(len(p) <= tl.HARD_MAX_IMAGES for p in tl.cut_video(items))


def test_each_video_segment_starts_with_the_screen_before_it():
    ev = Evidence("video", "h", [_narr(0), Item("image", t=1.0, image=b"a"), _narr(100), Item("image", t=101.0, image=b"b")])
    segs = tl.segments(ev)
    assert len(segs) == 2 and segs[0].context_image is None and segs[1].context_image.image == b"a"
    assert all(s.images <= 50 for s in segs)


def test_text_cuts_at_headings():
    items = [Item("heading", "A", anchor="#a"), Item("text", "x" * 20000), Item("heading", "B", anchor="#b"), Item("text", "y")]
    assert [p[0].text for p in tl.cut_text(items)] == ["A", "B"]


# ---- passes ----
def test_read_json_takes_fences_and_prose():
    assert read_json('```json\n[{"a":1}]\n```') == [{"a": 1}]
    assert read_json('Here you go: [{"a":1}] done') == [{"a": 1}]
    with pytest.raises(ValueError):
        read_json("nothing here")


def test_draft_fields_become_a_valid_tutorial():
    ev = Evidence("web", "abc", [], url="https://x")
    tut, errors = to_tutorial({"title": "T", "app": "A", "steps": [
        {**STEP, "verify": {"uia": [{"name": "Doc", "type": "Window"}]}}]}, ev)
    assert not errors and tut.steps[0].verify.uia.name == "Doc"
    assert tut.meta.source.hash == "abc"


@pytest.mark.parametrize("bad,why", [
    ({"action": "dance"}, "action"), ({"check": ""}, "check"), ({"source": {"t": "soon"}}, "source"),
    ({"action": "type"}, "value"), ({"target": {"label": "Nope", "kind": "spaceship"}}, "kind"),
    ({"params": {"x": 10, "y": 20}}, "screen position"), ({"verify": {"uia": [{"type": "Blob"}]}}, "UIA"),
])
def test_bad_steps_are_reported_not_dropped(bad, why):
    _, errors = to_tutorial({"title": "T", "app": "A", "steps": [{**STEP, **bad}]}, Evidence("web", "h", []))
    assert errors and any(why.casefold() in e.casefold() or "step 1" in e for e in errors)


def test_a_first_step_inside_an_unopened_dialog_goes_back():
    inside = {**STEP, "target": {"label": "Part", "kind": "button", "where": "New document dialog"}}
    ev = Evidence("web", "h", [])
    _, errors = to_tutorial({"title": "T", "app": "A", "steps": [inside]}, ev)
    assert errors and "nothing has opened it" in errors[0]
    _, errors = to_tutorial({"title": "T", "app": "A", "steps": [STEP, {**inside, "repeat_of": None}]}, ev)
    assert not errors


def test_a_last_choice_in_a_dialog_closes_it():
    def click(label, where):
        return {**STEP, "target": {"label": label, "kind": "button", "where": where}}
    ev = Evidence("web", "h", [])
    tut, errors = to_tutorial({"title": "T", "app": "A", "steps": [
        STEP, click("Part", "New dialog"), click("Plane", "tree"), click("Big", "Size dialog"), click("OK", "Size dialog"), STEP]}, ev)
    assert not errors
    assert tut.steps[1].params == {"click_type": "double"}      # nothing after it in the dialog
    assert tut.steps[3].params == {} and tut.steps[4].params == {}     # its own OK follows


def test_typing_in_another_file_clicks_its_tab_first():
    def typed(where, value="x"):
        return {**STEP, "action": "type", "target": {"label": "Editor", "kind": "field", "where": where}, "params": {"value": value}}
    new = {**STEP, "action": "type", "target": {"label": "File name field", "kind": "field"}, "params": {"value": "b.css"}}
    tab = {**STEP, "target": {"label": "a.html", "kind": "tab"}}
    again = {**STEP, "repeat_of": 1}
    tut, errors = to_tutorial({"title": "T", "app": "A", "steps": [
        typed("a.html, top"), new, typed("a.html, inside <head>"), typed("b.css, top"), tab, typed("a.html, end"), again]}, Evidence("web", "h", []))
    assert not errors
    labels = [s.target.label for s in tut.steps]
    assert labels == ["Editor", "File name field", "a.html", "Editor", "b.css", "Editor", "a.html", "Editor", "New"]
    added = tut.steps[2]
    assert added.confidence == "inferred" and added.verify.uia.selected and added.target.kind == "tab"
    assert tut.steps[8].repeat_of == 1


def test_a_failing_draft_goes_back_once_with_its_errors(tmp_path):
    seen = []

    def api(request):
        seen.append(request)
        good = len(seen) > 1
        return _reply(DRAFT if good else json.dumps({"title": "T", "app": "A", "steps": [{**STEP, "action": "dance"}]}))

    tut = merge(_client(tmp_path, api), "muse-spark-1.3", Evidence("web", "h", []), [{"part": 1, "actions": []}])
    assert len(seen) == 2 and tut.steps[0].action == "click"
    assert "step 1" in seen[1]["messages"][-1]["content"]


def test_a_draft_failing_twice_stops_the_compile(tmp_path):
    api = lambda r: _reply(json.dumps({"title": "T", "app": "A", "steps": [{**STEP, "action": "dance"}]}))
    with pytest.raises(CompileError, match="step 1"):
        merge(_client(tmp_path, api), "muse-spark-1.3", Evidence("web", "h", []), [])


# ---- the rules about gold, tools and source material ----
def test_prompts_contain_nothing_from_the_gold_files():
    tell = ["mug", "solidworks", "youtube", "offset entities", "revolve", "sweep", "front plane", "centerline", "thumbnail",
            "video-container", "video-details", "styles.css", "index.html", "live server", "mugedge", "fillet", "unsplash"]
    for p in sorted((ROOT / "engine/compile/passes/prompts").glob("*.md")):
        text = p.read_text(encoding="utf-8").casefold()
        assert not [t for t in tell if t in text], p.name


def test_shipped_code_touches_no_dropped_path():
    dropped = re.compile(r"""["'/\\](tools|sources|prototypes|assets)[/\\]|\bimport tools\b|\bfrom tools\b|scripts[/\\]download-video|\b0[0245] [A-Z][a-z]+\.md|Phase \d[^"'\n]*\.md""")
    for folder in ("engine", "overlay/main", "overlay/renderer", "overlay/shared", "deploy"):
        for p in (ROOT / folder).rglob("*"):
            if p.suffix in (".py", ".ts", ".html", ".mjs", ".css", ".toml") and "__pycache__" not in p.parts and "node_modules" not in p.parts:
                hits = [m.group(0) for m in dropped.finditer(p.read_text(encoding="utf-8", errors="replace"))]
                assert not hits, f"{p}: {hits}"


def test_shipped_code_names_no_private_note():
    """The planning notes, the people and the build phases stay out of what the public repo keeps."""
    private = re.compile(r"\b0[0245] (Context|Meta models|Base format|Architecture)\b|[Gg]lossary|\bKai\b|\b[Pp]hases? \d|\bP\d-\w|prototypes/"
                         r"|[Bb]aseten|[Ff]ireworks")
    me = Path(__file__).name
    for folder in ("engine", "overlay/main", "overlay/renderer", "overlay/shared", "overlay/test", "deploy", "tests", "scripts", "appmaps"):
        for p in (ROOT / folder).rglob("*"):
            if p.suffix in (".py", ".ts", ".html", ".mjs", ".css", ".toml", ".yaml", ".bat", ".md", ".jsonl") and p.name != me \
                    and "__pycache__" not in p.parts and "node_modules" not in p.parts and "out" not in p.parts:
                hits = [m.group(0) for m in private.finditer(p.read_text(encoding="utf-8", errors="replace"))]
                assert not hits, f"{p}: {sorted(set(hits))}"


def test_tutorial_sources_stay_out_of_git():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "sources/" in ignore and "cache/" in ignore


# ---- enrich ----
def _store(tmp_path, app="BoxCAD"):
    return AppMapStore(app, builtin_dir=tmp_path / "builtin", local=tmp_path / "local")


def _tut(*labels, kind="button"):
    steps = [{**STEP, "target": {"label": x, "kind": kind}} for x in labels]
    tut, errors = to_tutorial({"title": "T", "app": "BoxCAD", "steps": steps}, Evidence("web", "h", []))
    assert not errors
    return tut


def test_enrich_saves_new_entries_locally_and_fills_empty_step_fields(tmp_path):
    answer = json.dumps([{"label": "Lid", "menu_path": ["Insert", "Lid"], "aliases": ["Cap", "Lid"], "shortcut": "Ctrl+L", "source": "https://help.example.com/lid"},
                         {"label": "Made up", "menu_path": ["X"], "source": "https://help.example.com/x"},
                         {"label": "Handle", "menu_path": ["Y"]}])
    fake = Fake(answer=answer)
    store = _store(tmp_path)
    tut = _tut("Lid", "Handle")
    got = enrich(_client(tmp_path, fake), "muse-spark-1.3", tut, store)
    assert got == {"asked": 2, "found": 1, "searches": 1, "labels": ["Lid"]}
    c = store.local.root["Lid"]
    assert c.menu_path == ["Insert", "Lid"] and c.aliases == ["Cap"] and c.shortcut == "Ctrl+L" and c.source and c.seen is None
    assert "Handle" not in store.local.root                                    # no page behind it, not a docs fact
    assert tut.steps[0].target.menu_path == ["Insert", "Lid"]
    assert not list((tmp_path / "builtin").glob("*")) if (tmp_path / "builtin").exists() else True


def test_enrich_never_asks_about_what_is_known_and_never_overwrites(tmp_path):
    store = _store(tmp_path)
    store.add_facts("Lid", menu_path=["Mine"], source="https://mine")
    fake = Fake()
    assert new_controls(_tut("Lid"), store) == []
    assert enrich(_client(tmp_path, fake), "muse-spark-1.3", _tut("Lid"), store)["asked"] == 0
    assert fake.calls == [] and store.get("Lid").menu_path == ["Mine"]


def test_enrich_only_looks_up_named_controls(tmp_path):
    assert new_controls(_tut("the wall", kind="canvas"), _store(tmp_path)) == []


def test_a_failed_lookup_never_fails_the_compile(tmp_path):
    def api(request):
        raise __import__("engine.models.client", fromlist=["ModelError"]).ModelError("500")
    store = _store(tmp_path)
    got = enrich(_client(tmp_path, api), "muse-spark-1.3", _tut("Lid"), store, log=lambda s: None)
    assert got["found"] == 0


def test_search_queries_are_billed(tmp_path):
    fake = Fake(answer="[]")
    client = _client(tmp_path, fake)
    enrich(client, "muse-spark-1.3", _tut("Lid"), _store(tmp_path))
    row = json.loads((tmp_path / "costs.jsonl").read_text().splitlines()[0])
    assert row["searches"] == 1
    assert row["cost_usd"] == pytest.approx((10 * 1.25 + 5 * 4.25) / 1e6 + 0.0025, abs=1e-6)


# ---- a compiled `where` on the live finder ----
def test_where_finds_a_tag_by_its_attributes_among_others():
    from engine.live.locate.vscode import target_line
    code = '<body>\n<a href="#" class="thumbnail">\n<img />\n</a>\n</body>'
    assert target_line(code, 'index.html, in <a class="thumbnail"> after the class attribute', 1) == 2
    assert target_line(code, 'index.html, inside <a class="thumbnail">', 1) == 3
    assert target_line(code, 'index.html, in <a class="nope"> after the class attribute', 5) == 5
    assert target_line("", "styles.css, empty file", 7) == 1
    head = '<head>\n<link rel="stylesheet" href="s.css">\n<title>x</title>\n</head>\n<a>\n</a>'
    assert target_line(head, "index.html, inside <head> after stylesheet link", 9) == 3
    assert target_line('<div>\n<a href="#">thumb</a>\n<p></p>', "index.html, after the thumb link", 9) == 3


def test_a_toolbar_named_like_a_ribbon_tab_routes_through_it():
    from engine.live.locate.menu import named_tab
    assert named_tab("Features tab, CommandManager") == "Features"
    assert named_tab("Sketch Toolbar") == "Sketch" and named_tab("Features toolbar, top") == "Features"
    assert named_tab("Standard toolbar at top of window") is None and named_tab(None) is None


def test_solidworks_rules_read_a_tutorials_own_words():
    from engine.live.locate.solidworks import OK_LABEL, in_new_dialog
    assert in_new_dialog("New SOLIDWORKS Document dialog") and in_new_dialog("New document dialog")
    assert not in_new_dialog("Standard toolbar at top of window") and not in_new_dialog(None)
    for label in ("OK (green check)", "green check mark", "Green check mark", "OK"):
        assert OK_LABEL.match(label), label


def test_the_import_window_gets_the_score_in_plain_words():
    from engine.cli import _score_lines
    gold = parse_file(ROOT / "tutorials/mug-solidworks.md")
    lines = _score_lines(ev_score(gold))
    assert lines[0].startswith("Matches the hand-checked version: 100%") and "45 of 45" in lines[0]
    assert any("Allowing for" in x for x in lines)


def ev_score(gold):
    from engine.compile import eval as ev
    return ev.score(gold, gold, differences=ev.load_differences(ROOT / "tutorials/mug-solidworks.md"))


# ---- transcribe ----
def _wav(seconds=2, rate=16000):
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\0\0" * rate * seconds)
    return b.getvalue()


def test_transcribe_bills_by_the_second_and_replays_free(tmp_path):
    sent = []

    def asr(settings, wav):
        sent.append(settings)
        return {"transcript": "Hi.", "audioDurationMs": 3600000, "turns": [{"turnId": 1, "startMs": 0, "endMs": 900, "transcript": "Hi."}]}

    log = tmp_path / "costs.jsonl"
    c = ModelClient(mode="record", budget_usd=5, cassette_dir=tmp_path / "c", cost_log=log, transcribe_transport=asr)
    got = c.transcribe(_wav())
    assert got.turns[0]["transcript"] == "Hi." and got.cost_usd == pytest.approx(0.18)
    assert sent == [{"model": "muse-voice-transcribe-1.0", "audioEncoding": "WAV", "mode": "ENDPOINTING"}]
    again = c.transcribe(_wav())
    assert again.from_cassette and len(sent) == 1 and len(log.read_text().splitlines()) == 1


def test_transcribe_respects_the_cap(tmp_path):
    from engine.models.client import BudgetExceeded
    c = ModelClient(mode="record", budget_usd=0.00001, cassette_dir=tmp_path / "c", cost_log=tmp_path / "l", transcribe_transport=lambda s, w: {})
    with pytest.raises(BudgetExceeded):
        c.transcribe(_wav(10))


# ---- pipeline ----
def _pipeline(tmp_path, monkeypatch, fake, mode="record"):
    from engine.compile import pipeline as pl
    monkeypatch.setattr(pl, "CACHE", tmp_path / "compiled")
    monkeypatch.setattr(pl, "SCORES", tmp_path / "scores.jsonl")
    monkeypatch.setenv("GG_LOCAL_APPMAPS", str(tmp_path / "maps"))
    source = tmp_path / "t.txt"
    source.write_text("# Start\nOpen the app and click New.\n", encoding="utf-8")
    opts = Options(out=tmp_path / "out" / "t.compiled.md", model="muse-spark-1.3")
    return source, opts, _client(tmp_path, fake, mode=mode)


def test_compile_end_to_end_then_from_the_cache(tmp_path, monkeypatch):
    fake = Fake()
    source, opts, client = _pipeline(tmp_path, monkeypatch, fake)
    stages = []
    r = compile_tutorial(str(source), opts, client=client, progress=lambda s, p: stages.append((s, p)))
    assert r.steps == 1 and not r.cached and r.cost_usd > 0
    assert fake.calls == ["raw_actions", "tutorial", "enrich"]
    assert stages[-1] == ("Done", 1.0) and [p for _, p in stages] == sorted(p for _, p in stages)
    t = parse_file(r.path)
    assert t.meta.title == "Build a box" and t.meta.source.hash == r.source_hash and not t.meta.gold
    assert t.meta.compiled["prompts"] == prompts_version()
    again = compile_tutorial(str(source), opts, client=client)
    assert again.cached and again.path == r.path and len(fake.calls) == 3


def test_fresh_replays_recorded_replies_without_paying_twice(tmp_path, monkeypatch):
    fake = Fake()
    source, opts, client = _pipeline(tmp_path, monkeypatch, fake)
    compile_tutorial(str(source), opts, client=client)
    spent = client.spent_usd()
    opts.fresh = True
    r = compile_tutorial(str(source), opts, client=client)
    assert client.spent_usd() == spent and r.cost_usd == 0 and len(fake.calls) == 3


def test_a_gold_source_gets_scored_and_logged(tmp_path, monkeypatch):
    fake = Fake()
    source, opts, client = _pipeline(tmp_path, monkeypatch, fake)
    opts.gold = ROOT / "tutorials/mug-solidworks.md"
    r = compile_tutorial(str(source), opts, client=client)
    assert "fair" in r.score and r.score["gold_file"] == "mug-solidworks.md"
    row = json.loads((tmp_path / "scores.jsonl").read_text().splitlines()[0])
    assert row["raw_f1"] == round(r.score["raw"]["f1"], 3) and row["gold_sha"] == r.score["gold_sha"]


def test_no_actions_stops_with_a_clear_message(tmp_path, monkeypatch):
    def api(request):
        return _reply(json.dumps({"actions": []}))
    source, opts, client = _pipeline(tmp_path, monkeypatch, api)
    with pytest.raises(CompileError, match="no steps"):
        compile_tutorial(str(source), opts, client=client)


def test_unknown_inputs_are_explained(tmp_path, monkeypatch):
    source, opts, client = _pipeline(tmp_path, monkeypatch, Fake())
    with pytest.raises(SourceError, match="Can't find"):
        compile_tutorial("nothing-here.txt", opts, client=client)
    other = tmp_path / "f.xyz"
    other.write_text("x")
    with pytest.raises(SourceError, match="Can't read"):
        compile_tutorial(str(other), opts, client=client)
    long_paste = "Step one: click New.\nStep two: click Save."
    assert compile_tutorial(long_paste, opts, client=client).steps == 1


def test_replay_mode_spends_nothing(tmp_path, monkeypatch):
    source, opts, client = _pipeline(tmp_path, monkeypatch, Fake(), mode="replay")
    from engine.models.cassette import CassetteMiss
    with pytest.raises(CassetteMiss):
        compile_tutorial(str(source), opts, client=client)
    assert client.spent_usd() == 0


# ---- import, through the server ----
def test_import_and_open_over_the_websocket(tmp_path):
    import asyncio
    from websockets.asyncio.client import connect
    from engine.schema import messages as m
    from engine.server import serve
    port = 8797
    imported, opened = [], []

    def importer(msg, progress):
        imported.append(msg)
        progress("Reading", 0.5)
        return m.CompileDone(ok=True, path="x.md", title="T", steps=3, score=["raw: 1"])

    def opener(path):
        opened.append(path)
        raise RuntimeError("no such file")

    async def run():
        task = asyncio.create_task(serve(None, port=port, log=lambda s: None, importer=importer, opener=opener))
        await asyncio.sleep(0.2)
        async with connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({"type": "hello", "displays": []}))       # nothing loaded: no crash, no reply
            await ws.send(json.dumps({"type": "next"}))
            await ws.send(json.dumps({"type": "import", "url": "https://x", "start": "01:00"}))
            got = [json.loads(await asyncio.wait_for(ws.recv(), 3)) for _ in range(2)]
            await ws.send(json.dumps({"type": "open_tutorial", "path": "x.md"}))
            warn = json.loads(await asyncio.wait_for(ws.recv(), 3))
        task.cancel()
        return got, warn

    got, warn = asyncio.run(run())
    assert [g["type"] for g in got] == ["compile_progress", "compile_done"] and got[1]["steps"] == 3
    assert imported[0].url == "https://x" and imported[0].start == "01:00"
    assert opened == ["x.md"] and warn["type"] == "toast" and "no such file" in warn["text"]
