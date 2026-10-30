"""Input watcher's derived facts (live/inputs.py), window picking and VS Code's folder (live/windows.py),
and the pixel diff (live/capture.py). All pure; the Win32 parts are checked by the overlay check."""
import json

from PIL import Image

from engine.live.capture import changed, changed_share, crop, for_model
from engine.live.inputs import InputEvent, Recent
from engine.live.windows import Win, folder_from_title, folder_from_workspace_json, pick, vscode_folder


def test_idle_counts_keys_and_clicks_not_moves():
    t = [10.0]
    r = Recent(clock=lambda: t[0])
    assert r.idle_s() > 1e6
    r.add(InputEvent("key", 0, 0, 10.0))
    t[0] = 11.5
    r.add(InputEvent("move", 5, 5, 11.4))
    assert r.idle_s() == 1.5


def test_keys_are_recorded_without_which_key():
    ev = InputEvent("key", 1, 2, 3.0)
    assert set(vars(ev)) == {"kind", "x", "y", "t", "button"} and ev.button == ""


def test_moves_are_thinned_and_work_area_spans_recent_clicks():
    t = [100.0]
    r = Recent(clock=lambda: t[0])
    for i in range(10):
        r.add(InputEvent("move", i, i, 100.0 + i * 0.01))
    assert sum(e.kind == "move" for e in r.events) == 1
    r.add(InputEvent("down", 100, 200, 100.0, "left"))
    r.add(InputEvent("down", 300, 250, 100.5, "left"))
    assert r.work_area(pad=10) == (90, 190, 220, 70)
    t[0] = 200.0
    assert r.work_area() is None


def test_listeners_get_events_and_a_broken_one_doesnt_stop_the_rest():
    got = []
    r = Recent()
    r.listeners.append(lambda e: 1 / 0)
    r.listeners.append(got.append)
    r.add(InputEvent("down", 1, 1, 1.0, "left"))
    assert len(got) == 1


def test_pick_window_by_kind_skipping_ours_and_minimised():
    wins = [Win(1, "GhostGuide overlay", (0, 0, 100, 100)), Win(2, "Inbox - Google Chrome", (0, 0, 10, 10), minimized=True),
            Win(3, "Document - Google Chrome", (0, 0, 50, 50)), Win(4, "index.html - youtube-clone - Visual Studio Code", (0, 0, 9, 9))]
    assert pick(wins, "Browser").hwnd == 3
    assert pick(wins, "youtube-clone - Visual Studio Code").hwnd == 4
    assert pick(wins, "Blender") is None


def test_vscode_folder_from_title_and_workspace_storage(tmp_path):
    assert folder_from_title("index.html - youtube-clone - Visual Studio Code") == "youtube-clone"
    assert folder_from_title("youtube-clone - Visual Studio Code") == "youtube-clone"
    assert folder_from_title("Document - Google Chrome") is None
    assert str(folder_from_workspace_json('{"folder": "file:///c%3A/Users/x/youtube-clone"}')).replace("\\", "/") == "c:/Users/x/youtube-clone"
    proj = tmp_path / "youtube-clone"
    proj.mkdir()
    ws = tmp_path / "storage" / "abc"
    ws.mkdir(parents=True)
    (ws / "workspace.json").write_text(json.dumps({"folder": proj.as_uri()}), encoding="utf-8")
    assert vscode_folder("youtube-clone - Visual Studio Code", storage=tmp_path / "storage") == proj
    assert vscode_folder("other - Visual Studio Code", storage=tmp_path / "storage") is None


def test_pixel_diff_ignores_small_noise_and_sees_real_change():
    a = Image.new("L", (800, 400), 30)
    b = a.copy()
    b.putpixel((5, 5), 255)                         # a caret blink
    assert not changed(a, b)
    c = a.copy()
    c.paste(200, (0, 0, 400, 100))                  # a panel opened
    assert changed(a, c) and changed_share(a, c) > 0.1
    assert changed(a, Image.new("L", (400, 400), 30))   # different size: everything changed


def test_crop_and_model_copy():
    img = Image.new("RGB", (1000, 500))
    assert crop(img, (150, 60, 100, 50), origin=(100, 50), pad=10).size == (120, 70)
    png, scale = for_model(Image.new("RGB", (2560, 1600)))
    assert scale == 0.5 and png[:4] == b"\x89PNG"
