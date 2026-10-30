import pytest

PIL = pytest.importorskip("PIL.Image")

from engine.live.scheme import pick_scheme, ring_luminance, scheme_for
from engine.schema.messages import Box


def img(color, size=(400, 300)):
    return PIL.new("RGB", size, color)


def test_light_and_dark_app():
    box = Box(x=150, y=120, w=60, h=30)
    assert scheme_for(ring_luminance(img((243, 243, 243)), box)) == "light"     # SolidWorks grey-white
    assert scheme_for(ring_luminance(img((30, 30, 30)), box)) == "dark"          # VS Code Dark+


def test_ring_ignores_the_target_itself():
    im = img((20, 20, 20))
    box = Box(x=150, y=120, w=60, h=30)
    im.paste((255, 255, 255), (150, 120, 210, 150))        # a white button on a dark app
    assert scheme_for(ring_luminance(im, box)) == "dark"


def test_threshold_and_origin():
    box = Box(x=1100, y=700, w=20, h=20)
    grab = img((128, 128, 128), (116, 116))                 # cropped grab whose top-left is (1052, 652)
    lum = ring_luminance(grab, box, origin=(1052, 652))
    assert lum == pytest.approx(128 / 255, abs=0.01) and scheme_for(lum) == "light"
    assert scheme_for(0.45) == "dark" and scheme_for(0.46) == "light"


def test_box_outside_image_and_fallbacks():
    assert ring_luminance(img((0, 0, 0), (50, 50)), Box(x=500, y=500, w=10, h=10)) is None
    assert scheme_for(None, fallback="dark") == "dark"
    assert pick_scheme(Box(x=0, y=0, w=1, h=1), override="dark") == ("dark", None)
