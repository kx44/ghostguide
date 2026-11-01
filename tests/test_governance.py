"""The governance measures in docs/privacy-and-security.md: each one claimed there has a test here."""
import ast
import asyncio
import contextlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from engine import activity, config
from engine.basefile.parse import parse_text
from engine.basefile.validate import validate_tutorial
from engine.compile.adapters import SourceError, web
from engine.live import execute
from engine.live.execute import can_do, needs_confirm
from engine.live.inputs import InputEvent, Recent
from engine.live.verify import Ladder, Snapshot, Tracker, Verdict
from engine.models import glimmer
from engine.models.client import ModelClient, ModelError, image_part, text_part
from engine.schema.messages import Box
from engine.schema.tutorial import FileCheck, Source, Step, Target

ROOT = Path(__file__).resolve().parent.parent
BOX = Box(x=1, y=1, w=10, h=10)
KEY = "sk-test-do-not-log-1234567890"


def step(action="click", kind="button", label="Save", **params):
    return Step(n=1, title="T", action=action, target=Target(label=label, kind=kind), params=params, check="c",
                source=Source(t="00:01"), confidence="high")


def client(tmp_path, reply=None, **kw):
    reply = reply or {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}}
    return ModelClient(mode="live", budget_usd=5, cassette_dir=tmp_path / "c", cost_log=tmp_path / "cost.jsonl",
                       transport=lambda r: reply, **kw)


def picture(tag="check-step-1", png=b"\x89PNG" + b"x" * 300):
    return dict(model=config.SPARK, max_tokens=10, tag=tag,
                messages=[{"role": "user", "content": [text_part("question"), image_part(png)]}])


# ---- what leaves the PC is written down, without its contents ----
def test_a_send_is_logged_with_its_size_and_never_its_contents(tmp_path):
    client(tmp_path).chat(**picture())
    rows = activity.read()
    assert len(rows) == 1 and rows[0]["kind"] == "sent" and rows[0]["images"] == 1 and rows[0]["screen"] is True
    assert rows[0]["bytes"] > 300
    raw = activity.LOG.read_text(encoding="utf-8")
    assert "base64" not in raw and "question" not in raw and "PNG" not in raw
    assert activity.pictures_sent() == 1


def test_compiling_someone_elses_tutorial_isnt_counted_as_your_screen(tmp_path):
    client(tmp_path).chat(**picture(tag="extract-1"))
    assert activity.read()[0]["screen"] is False and activity.pictures_sent() == 0


def test_a_recorded_answer_sends_nothing(tmp_path):
    c = ModelClient(mode="record", budget_usd=5, cassette_dir=tmp_path / "c", cost_log=tmp_path / "cost.jsonl",
                    transport=lambda r: {"choices": [{"message": {"content": "ok"}}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}})
    c.chat(**picture())
    c.chat(**picture())
    assert len(activity.read()) == 1


def test_glimmer_is_logged_too():
    glimmer.glimmer_modal("https://x.modal.run", post=lambda url, body: {"result": "done"})(step(), _png())
    row = activity.read()[0]
    assert row["to"] == "x.modal.run" and row["images"] == 1 and row["screen"] is True


def test_an_acted_step_says_what_kind_of_input_and_not_the_text():
    activity.acted(4, "Name it", ["click", "keys", "text"])
    assert activity.read()[0]["ops"] == ["click", "keys", "text"]


def _png():
    import io

    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (8, 8)).save(buf, "PNG")
    return buf.getvalue()


# ---- the switch: nothing from the screen leaves ----
def test_local_only_stops_screens_at_the_door_but_not_compiling(tmp_path):
    activity.set_local_only(True)
    c = client(tmp_path)
    with pytest.raises(activity.LocalOnly):
        c.chat(**picture())
    assert activity.read() == []
    c.chat(**picture(tag="merge"))          # someone else's tutorial isn't your screen
    with pytest.raises(activity.LocalOnly):
        glimmer.glimmer_modal("https://x.modal.run", post=lambda u, b: {"result": "done"})(step(), _png())


def _tracker(ladder, s, app="MyApp", hidden=False):
    from PIL import Image

    tut = parse_text("---\ntitle: T\napp: A\nsource: {type: web}\n---\n", "t")
    tut.steps = [s]
    frames = iter([Image.new("L", (64, 64), 0)] + [Image.new("L", (64, 64), 255)] * 9)
    t = Tracker(tut, app, None, lambda w: [], ladder=ladder, grab=lambda st: next(frames))
    t.current_n, t.hidden = 1, hidden
    return t


def _ask(t, s, times=3):
    from engine.live.verify import _StepWatch
    w = _StepWatch(shown_at=0.0)
    return [t._diff(s, w, 100.0 + i * 10) for i in range(times)]


def test_the_models_do_get_the_apps_own_window_when_nothing_holds_it_back():
    asked = []
    s = step(kind="button")
    _ask(_tracker(Ladder(glimmer=lambda st, png: asked.append(st) or Verdict("done")), s), s)
    assert asked


def test_a_step_naming_another_window_never_sends_it_to_a_model():
    asked = []
    s = step(kind="window", label="Inbox - Mail")
    out = _ask(_tracker(Ladder(glimmer=lambda st, png: asked.append(st) or Verdict("done")), s), s)
    assert not asked and any("isn't the tutorial's app" in v.why for v in out)
    assert any(r["kind"] == "withheld" for r in activity.read())


def test_hidden_means_free_checks_only():
    asked = []
    s = step()
    _ask(_tracker(Ladder(glimmer=lambda st, png: asked.append(st) or Verdict("done")), s, hidden=True), s)
    assert not asked


def test_the_switch_and_a_secret_title_hold_the_ladder_back():
    asked = []
    s = step()
    t = _tracker(Ladder(glimmer=lambda st, png: asked.append(st) or Verdict("done")), s)
    t.gate = lambda: activity.title_withheld(".env - proj - Visual Studio Code")
    assert any("secrets file" in v.why for v in _ask(t, s))
    t2 = _tracker(Ladder(glimmer=lambda st, png: asked.append(st) or Verdict("done")), s)
    activity.set_local_only(True)
    _ask(t2, s)
    assert not asked


@pytest.mark.parametrize("title,held", [
    (".env - proj - Visual Studio Code", True), ("● .env.local - proj - Visual Studio Code", True),
    ("server.pem - x", True), ("id_rsa - Notepad", True), ("passwords.kdbx - KeePass", True), ("Credentials.json - x", True),
    ("index.html - youtube-clone - Visual Studio Code", False), ("SOLIDWORKS Design Standard 2026 - Part1", False),
    ("styles.css - environment - x", False), (None, False)])
def test_titles_that_name_secrets(title, held):
    assert bool(activity.title_withheld(title)) is held


def test_a_finder_look_is_stopped_by_the_gate(monkeypatch):
    from engine import cli
    from engine.live import windows

    class W:
        title = "secrets.yaml - proj - Visual Studio Code"
    monkeypatch.setattr(windows, "find", lambda part: W)
    assert "secrets file" in cli._kept_on_pc("Visual Studio Code")
    W.title = "index.html - proj - Visual Studio Code"
    assert cli._kept_on_pc("Visual Studio Code") is None
    activity.set_local_only(True)
    assert "stay on this PC" in cli._kept_on_pc("Visual Studio Code")


def test_the_tray_line_says_what_is_true():
    assert "nothing" in activity.privacy_line(False).casefold()
    assert "0 pictures" in activity.privacy_line(True)
    activity.set_local_only(True)
    assert "Nothing from your screen" in activity.privacy_line(True)


def test_the_switch_works_from_the_overlay():
    from engine.live.player import Player
    from engine.live.session import Session
    from engine.basefile.parse import parse_file

    p = Player(Session(parse_file("tutorials/youtube-clone-vscode.md")), scheme_override="dark")
    out = p.handle({"type": "toggle_local"})
    assert activity.local_only() and out[0].local_only is True and "Nothing" in out[0].privacy
    p.handle({"type": "toggle_local"})
    assert not activity.local_only()


# ---- Contributor only by choice ----
def _rung_model(monkeypatch, value):
    seen = {}
    monkeypatch.setenv("CHECK_MODELS", "on")
    monkeypatch.delenv("GLIMMER_MODAL_URL", raising=False)
    monkeypatch.setenv("SCREENS_MAY_TRAIN", value)

    class Fake:
        def chat(self, **kw):
            seen.update(kw)
            from engine.models.client import Reply
            return Reply(text='{"result":"done"}')
    monkeypatch.setattr("engine.models.client.ModelClient", Fake)
    glimmer.check_stages()[1](step(), b"png")
    return seen["model"]


def test_screens_go_to_standard_spark_unless_you_said_yes(monkeypatch):
    assert _rung_model(monkeypatch, "off") == config.SPARK
    assert _rung_model(monkeypatch, "on") == config.SPARK_CONTRIBUTOR


# ---- input watching ----
def test_the_watcher_keeps_no_key_code():
    assert set(InputEvent.__dataclass_fields__) == {"kind", "x", "y", "t", "button"}
    src = (ROOT / "engine/live/inputs.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    # VKey and MakeCode are only ever written to, to zero them. Nothing reads them.
    reads = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute) and n.attr in ("VKey", "MakeCode") and isinstance(n.ctx, ast.Load)]
    assert reads == []
    assert not re.search(r"\b(open|write_text|write_bytes|\.write)\(", src), "the watcher writes nothing to disk"


def test_nothing_is_kept_while_no_overlay_is_connected():
    r = Recent(clock=lambda: 10.0)
    r.add(InputEvent("down", 1, 1, 9.0, "left"))
    r.pause(True)
    assert not r.clicks() and r.idle_s() == 1e9
    r.add(InputEvent("key", 0, 0, 9.5))
    assert not r.events
    r.pause(False)
    r.add(InputEvent("key", 0, 0, 9.5))
    assert len(r.events) == 1


# ---- Do it for me ----
@pytest.mark.parametrize("keys", [["Alt", "Tab"], ["alt", "esc"], ["Ctrl", "Esc"], ["Ctrl", "Shift", "Escape"], ["Alt", "Space"], ["Ctrl", "Alt", "Delete"]])
def test_keys_that_leave_the_app_are_never_pressed(keys):
    assert not can_do(step("shortcut", keys=keys), None)


def test_a_normal_shortcut_still_runs():
    assert can_do(step("shortcut", keys=["Ctrl", "1"]), None)


def test_delete_takes_a_second_press_whatever_found_it():
    assert needs_confirm(step("shortcut", keys=["Delete"]), "uia", None)
    assert not needs_confirm(step("shortcut", keys=["Ctrl", "S"]), "uia", None)


@pytest.mark.parametrize("value,ok", [("MugEdge", True), ("line\nrm -rf /", False), ("a\tb", False), ("x" * 201, False), ("x" * 200, True)])
def test_what_it_will_type(value, ok):
    assert can_do(step("type", kind="field", value=value), BOX) is ok


@pytest.mark.parametrize("then,ok", [("Enter", True), ("Tab", True), ("Delete", False), ("Alt", False)])
def test_only_enter_or_tab_after_typing(then, ok):
    assert can_do(step("type", kind="field", value="5", then_key=then), BOX) is ok


def test_typing_stops_the_moment_the_app_isnt_in_front():
    sent, left = [], iter([True, True, False])
    done = execute._text("abcdef", still_ok=lambda: next(left), send=sent.append)
    assert done is False and sent == ["a", "b"]
    assert execute._text("ab", send=sent.append) is True


def test_an_act_goes_in_the_log_and_a_refusal_doesnt():
    from engine.basefile.parse import parse_file
    from engine.live.player import Player
    from engine.live.session import Session

    class Ex:
        why = None

        def run(self, ops):
            return self.why
    tut = parse_file("tutorials/mug-solidworks.md")
    p = Player(Session(tut), scheme_override="light", executor=Ex())
    s = p.session
    while s.step.action != "shortcut":
        s.next()
    p.executor.why = "Bring it to the front first"
    assert p._do_it()[0].kind == "warn" and activity.read() == []
    p.executor.why = None
    p._do_it()
    assert activity.read()[0]["kind"] == "acted" and activity.read()[0]["step"] == s.step.n


def test_do_it_has_no_hotkey():
    assert "do_it" not in (ROOT / "overlay/main/hotkeys.ts").read_text(encoding="utf-8")


# ---- tutorial files are untrusted ----
BAD = """---
title: T
app: A
source: {{type: web, url: "{url}"}}
---
## Step 1 — S
```yaml
action: click
target: {{label: L, kind: button}}
check: c
verify: {{file: {{path: "{path}", contains: x}}}}
source: {{anchor: "#a"}}
confidence: high
```
"""


@pytest.mark.parametrize("path", ["../../secret.txt", "..\\secret.txt", "C:\\Users\\x\\id_rsa", "/etc/passwd", "a/../../b"])
def test_a_file_check_cant_leave_the_folder(path, tmp_path):
    tut = parse_text(BAD.format(url="https://e.com/", path=path.replace("\\", "\\\\")), "t")
    assert any("relative to the working folder" in e for e in validate_tutorial(tut).errors)
    (tmp_path / "in").mkdir()
    (tmp_path / "secret.txt").write_text("x", encoding="utf-8")
    assert Snapshot("a", lambda w: [], folder=tmp_path / "in").read("../secret.txt") is None


def test_a_file_inside_the_folder_still_reads(tmp_path):
    (tmp_path / "index.html").write_text("hello", encoding="utf-8")
    assert Snapshot("a", lambda w: [], folder=tmp_path).read("index.html") == "hello"


@pytest.mark.parametrize("url,ok", [("https://e.com/a", True), ("javascript:alert(1)", False), ("file:///c:/x", False), ("TBD", True)])
def test_a_source_must_be_a_web_link(url, ok):
    tut = parse_text(BAD.format(url=url, path="a.txt"), "t")
    assert validate_tutorial(tut).ok is ok


def test_play_refuses_a_file_that_fails_its_checks(tmp_path, capsys):
    from engine.cli import main

    bad = tmp_path / "bad.md"
    bad.write_text(BAD.format(url="https://e.com/", path="../../x"), encoding="utf-8")
    assert main(["play", str(bad), "--console", "--locate", "pins"]) == 2
    assert "won't play" in capsys.readouterr().err


def test_a_saved_page_cant_reach_a_picture_outside_its_folder(tmp_path):
    (tmp_path / "secret.png").write_bytes(b"x")
    (tmp_path / "page").mkdir()
    (tmp_path / "page" / "a.png").write_bytes(b"y")
    load = web._local_loader(tmp_path / "page" / "p.html")
    assert load("../secret.png") is None and load(str(tmp_path / "secret.png")) is None and load("file:///x") is None
    assert load("a.png") == b"y"


def test_model_tools_can_only_describe_never_do():
    from engine.models.tools import LOCATE_TOOLS
    assert {t["function"]["name"] for t in LOCATE_TOOLS} <= {"point_at", "draw_line", "menu_path", "not_found"}


def test_video_links_only_go_to_video_sites():
    from engine.compile.pipeline import VIDEO_HOSTS
    assert VIDEO_HOSTS.match("https://www.youtube.com/watch?v=x") and not VIDEO_HOSTS.match("https://evil.example/youtube.com/")


# ---- fetching ----
@pytest.mark.parametrize("url", ["http://localhost:8765/", "http://127.0.0.1/admin", "http://[::1]/", "http://10.0.0.5/", "http://192.168.1.1/",
                                 "http://169.254.169.254/latest/meta-data", "http://printer.local/", "file:///c:/x", "ftp://example.com/"])
def test_this_pc_and_its_network_are_never_fetched(url):
    with pytest.raises(SourceError):
        web.guard_url(url)


def test_a_redirect_is_checked_too(monkeypatch):
    import httpx

    calls = []

    @contextlib.contextmanager
    def stream(method, url, **kw):
        calls.append(url)
        yield httpx.Response(302, headers={"location": "http://127.0.0.1/secret"}, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx, "stream", stream)
    monkeypatch.setattr(web, "is_public_host", lambda h: h != "127.0.0.1")
    with pytest.raises(SourceError, match="local network"):
        web.fetch_page("https://example.com/a")
    assert calls == ["https://example.com/a"]


def test_a_huge_page_is_left_unread(monkeypatch):
    import httpx

    @contextlib.contextmanager
    def stream(method, url, **kw):
        yield httpx.Response(200, content=b"x" * 100, request=httpx.Request("GET", url))
    monkeypatch.setattr(httpx, "stream", stream)
    monkeypatch.setattr(web, "guard_url", lambda u: None)
    monkeypatch.setattr(web, "MAX_PAGE_BYTES", 10)
    with pytest.raises(SourceError, match="left unread"):
        web.fetch_page("https://example.com/")


def test_a_bad_link_in_a_file_gets_a_message_not_an_endless_wait(monkeypatch):
    from engine.basefile.parse import parse_file
    from engine.live.source import Sources

    s = Sources(parse_file("tutorials/mug-solidworks.md"))
    monkeypatch.setattr(web, "fetch_page", lambda url, timeout=0: (_ for _ in ()).throw(KeyError("boom")))
    s.fetch("https://example.com/")
    assert "couldn't be read" in s.refused


# ---- the local socket ----
def _serve_and(fn):
    from engine.server import serve

    async def run():
        task = asyncio.create_task(serve(None, port=8798, log=lambda *_: None, inputs=fn.inputs))
        await asyncio.sleep(0.2)
        try:
            return await fn()
        finally:
            task.cancel()
    return asyncio.run(run())


def test_a_web_page_cant_connect_but_the_overlay_can():
    from websockets.asyncio.client import connect
    from websockets.exceptions import InvalidStatus

    async def go():
        with pytest.raises(InvalidStatus) as e:
            await connect("ws://127.0.0.1:8798", origin="https://evil.example")
        assert e.value.response.status_code == 403
        with pytest.raises(InvalidStatus):
            await connect("ws://127.0.0.1:8798", origin="null")
        async with await connect("ws://127.0.0.1:8798") as ws:
            await ws.ping()
            return True
    go.inputs = None
    assert _serve_and(go)


def test_a_bad_message_doesnt_cut_the_overlay_off():
    from websockets.asyncio.client import connect

    async def go():
        async with await connect("ws://127.0.0.1:8798") as ws:
            for bad in ("[1,2]", "null", "{", '"x"', '{"type":"nonsense"}'):
                await ws.send(bad)
            await ws.ping()
            return True
    go.inputs = None
    assert _serve_and(go)


def test_watching_runs_only_while_the_overlay_is_connected():
    from websockets.asyncio.client import connect

    recent = Recent()

    async def go():
        assert recent.paused
        async with await connect("ws://127.0.0.1:8798") as ws:
            await ws.ping()
            await asyncio.sleep(0.05)
            assert not recent.paused
        await asyncio.sleep(0.2)
        assert recent.paused
        return True
    go.inputs = recent
    assert _serve_and(go)


def test_the_engine_listens_on_this_pc_only():
    src = (ROOT / "engine/server.py").read_text(encoding="utf-8")
    assert re.search(r'ws_serve\(handler, "127\.0\.0\.1"', src) and "0.0.0.0" not in src


# ---- the overlay's windows ----
OVERLAY = ROOT / "overlay"


def test_every_window_is_sandboxed_and_cant_navigate():
    for name in ("main.ts", "sourceWindow.ts"):
        src = (OVERLAY / "main" / name).read_text(encoding="utf-8")
        windows = src.count("new BrowserWindow(") + src.count("new WebContentsView(")
        safe = src.count("contextIsolation: true, nodeIntegration: false")
        assert windows and windows == safe and src.count("sandbox: true") == windows, name
        assert src.count('"will-navigate"') == windows and src.count("setWindowOpenHandler") == windows, name


def test_every_permission_request_is_denied():
    assert "setPermissionRequestHandler((_wc, _perm, answer) => answer(false))" in (OVERLAY / "main/main.ts").read_text(encoding="utf-8")


@pytest.mark.parametrize("page", ["index.html", "import.html", "source.html"])
def test_every_page_has_a_strict_content_policy(page):
    html = (OVERLAY / "renderer" / page).read_text(encoding="utf-8")
    policy = re.search(r'Content-Security-Policy" content="([^"]+)"', html).group(1)
    # The source window's pictures are the one thing that may come from the web, and only over https.
    rules = [r.strip() for r in policy.split(";")]
    assert "script-src 'self'" in policy and "unsafe-eval" not in policy
    assert not [r for r in rules if "http" in r and not (page == "source.html" and r == "img-src file: https:")]
    assert "'unsafe-inline'" not in policy.split("script-src")[1].split(";")[0]


def test_the_source_page_shows_the_tutorials_words_as_text():
    src = (OVERLAY / "renderer/shell/sourceView.ts").read_text(encoding="utf-8")
    assert "innerHTML" not in src and "textContent = b.text" in src


# ---- keys ----
def test_keys_stay_out_of_logs_cassettes_and_errors(tmp_path, monkeypatch):
    import httpx

    monkeypatch.setenv("META_API_KEY", KEY)
    monkeypatch.setenv("META_BASE_URL", "https://api.example/v1")
    monkeypatch.setattr(httpx, "post", lambda url, json, headers, timeout: httpx.Response(401, text="no", request=httpx.Request("POST", url)))
    c = ModelClient(mode="record", budget_usd=5, cassette_dir=tmp_path / "c", cost_log=tmp_path / "cost.jsonl")
    with pytest.raises(ModelError) as e:
        c.chat(**picture())
    assert KEY not in str(e.value)
    c2 = client(tmp_path)
    c2.mode = "record"
    c2.chat(**picture())
    for p in [activity.LOG, tmp_path / "cost.jsonl", *(tmp_path / "c").glob("*")]:
        assert KEY not in p.read_text(encoding="utf-8")


def test_cassettes_hold_no_pictures(tmp_path):
    c = client(tmp_path)
    c.mode = "record"
    c.chat(**picture())
    saved = next((tmp_path / "c").glob("*.json")).read_text(encoding="utf-8")
    assert "base64" not in saved and "sha256:" in saved


@pytest.mark.parametrize("url,ok", [("https://api.meta.ai/v1", True), ("http://api.meta.ai/v1", False), ("http://127.0.0.1:9/v1", True), ("http://localhost/v1", True),
                                    ("http://127.0.0.1.evil.example/v1", False), ("ftp://x/", False)])
def test_keys_only_travel_over_https(url, ok):
    assert config.is_secure(url) is ok


def test_the_key_isnt_sent_over_plain_http(monkeypatch):
    from engine.models.client import _http_send
    monkeypatch.setenv("META_API_KEY", KEY)
    monkeypatch.setenv("META_BASE_URL", "http://api.example/v1")
    with pytest.raises(ModelError, match="without https"):
        _http_send({"model": "m"})


def test_a_screenshot_isnt_sent_to_glimmer_over_plain_http():
    with pytest.raises(ValueError, match="without https"):
        glimmer.glimmer_modal("http://x.modal.run")(step(), _png())


def test_the_env_file_is_ignored_and_the_example_holds_no_values():
    assert subprocess.run(["git", "check-ignore", "-q", ".env"], cwd=ROOT).returncode == 0
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    for key in ("META_API_KEY", "GLIMMER_MODAL_TOKEN", "GLIMMER_MODAL_URL"):
        assert re.search(rf"^{key}=$", example, re.M), key


def test_no_secret_from_the_local_env_is_in_a_tracked_file():
    """Reads the values only to compare; a failure names the file and the setting, never the value."""
    env = ROOT / ".env"
    if not env.exists():
        pytest.skip("no local .env")
    secrets = {}
    for line in env.read_text(encoding="utf-8").splitlines():
        k, _, v = line.partition("=")
        v = v.strip().strip('"\'')
        if k.strip() in ("META_API_KEY", "GLIMMER_MODAL_TOKEN", "GLIMMER_MODAL_URL") and len(v) >= 8:
            secrets[k.strip()] = v
    files = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.split("\0")
    for f in filter(None, files):
        p = ROOT / f
        if p.is_file() and p.stat().st_size < 5_000_000:
            text = p.read_text(encoding="utf-8", errors="replace")
            for k, v in secrets.items():
                assert v not in text, f"{f} holds the value of {k}"


# ---- cached data ----
def test_nothing_in_the_live_loop_writes_a_picture_to_disk():
    for name in ("capture.py", "verify.py", "player.py", "scheme.py", "locate/vision.py", "locate/menu.py", "locate/tooltip.py", "../models/glimmer.py"):
        src = (ROOT / "engine/live" / name).read_text(encoding="utf-8")
        for m in re.finditer(r"\.save\(([^)]*)\)", src):
            assert m.group(1).split(",")[0].strip() in ("buf", "out"), f"{name}: {m.group(0)}"
        assert "write_bytes" not in src, name


def test_forget_lists_then_removes_and_keeps_the_spend_log(tmp_path, monkeypatch):
    from engine import forget

    logs, sessions, maps = tmp_path / "logs", tmp_path / "sessions", tmp_path / "maps"
    for d in (logs, sessions, maps):
        d.mkdir()
    (logs / forget.COST_LOG_NAME).write_text("{}", encoding="utf-8")
    (logs / "activity.jsonl").write_text("{}", encoding="utf-8")
    (sessions / "t.json").write_text("{}", encoding="utf-8")
    (maps / "vscode.yaml").write_text("x: 1", encoding="utf-8")
    monkeypatch.setattr(forget, "_places", lambda: [("a", logs), ("b", sessions), ("c", maps), ("d", tmp_path / "gone")])
    held = forget.holdings()
    assert [h["what"] for h in held] == ["a", "b", "c"] and held[0]["bytes"] == 2       # the spend log isn't counted as removable
    for h in held:
        forget.remove(Path(h["path"]))
    assert [p.name for p in logs.iterdir()] == [forget.COST_LOG_NAME]
    assert not list(sessions.iterdir()) and not list(maps.iterdir())


def test_forget_only_names_its_own_places():
    from engine import forget

    for _, p in forget._places():
        assert ".env" not in str(p) and p != config.ROOT and p != config.TUTORIALS and p != config.COMPILED


@pytest.mark.skipif(sys.platform != "win32", reason="junctions are Windows")
def test_forget_removes_a_junction_and_not_what_it_points_at(tmp_path):
    from engine import forget

    keep = tmp_path / "keep"
    keep.mkdir()
    (keep / "precious.txt").write_text("x", encoding="utf-8")
    folder = tmp_path / "cache"
    folder.mkdir()
    subprocess.run(["cmd", "/c", "mklink", "/J", str(folder / "link"), str(keep)], check=True, capture_output=True)
    assert forget._size(folder) == 0
    forget.remove(folder)
    assert not list(folder.iterdir()) and (keep / "precious.txt").exists()


def test_activity_command_prints_no_contents(tmp_path, capsys):
    from engine.cli import main

    client(tmp_path).chat(**picture())
    assert main(["activity"]) == 0
    out = capsys.readouterr().out
    assert "Pictures of your screen: 1" in out and "question" not in out


# ---- the Modal endpoint ----
def _modal_helpers():
    src = (ROOT / "deploy/modal_glimmer.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    keep = [n for n in tree.body if (isinstance(n, ast.FunctionDef) and n.name in ("authorised", "acceptable"))
            or (isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") in ("MAX_IMAGE_B64", "IMAGE_MIMES"))]
    ns = {}
    exec(compile(ast.Module(keep, []), "modal", "exec"), ns)
    return ns


def test_the_endpoint_fails_closed():
    f = _modal_helpers()["authorised"]
    assert f("Bearer abc", "abc") and not f("Bearer abd", "abc") and not f(None, "abc")
    assert not f("Bearer ", "") and not f("", "")


def test_the_endpoint_takes_a_picture_of_a_sensible_size():
    h = _modal_helpers()
    assert h["acceptable"]("aGk=", "image/jpeg") and not h["acceptable"]("", "image/jpeg")
    assert not h["acceptable"]("aGk=", "text/html") and not h["acceptable"]("x" * (h["MAX_IMAGE_B64"] + 1), "image/png")
