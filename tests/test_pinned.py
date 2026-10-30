import pytest
from pydantic import ValidationError

from engine.live.locate.pinned import Pin, Pins
from engine.live.pinning import box_from

FIX = "tests/fixtures/pins/youtube-clone-vscode.yaml"


def test_fixture_pins_and_same_as():
    p = Pins.load(FIX)
    assert p.box(1).x == 214 and p.box(19) == p.box(14) and p.box(11) == p.box(6)
    assert p.box(23) is None and p.line(1) is None


def test_lines_round_trip(tmp_path):
    p = Pins(steps={3: Pin(line=((10, 20), (110, 20))), 4: Pin(same_as=3)})
    p.dump(tmp_path / "p.yaml")
    q = Pins.load(tmp_path / "p.yaml")
    assert q.line(4).end == (110, 20) and q.box(3).w == 100 and q.box(3).h == 1
    assert Pins.load(tmp_path / "missing.yaml").steps == {}


def test_bad_pins():
    with pytest.raises(ValidationError):
        Pin(box=(1, 2, 3, 4), same_as=2)
    with pytest.raises(ValidationError):
        Pin(box=(1, 2, 0, 4))
    with pytest.raises(ValueError):
        Pins(steps={1: Pin(same_as=2), 2: Pin(same_as=1)}).box(1)


def test_box_from_corners():
    assert box_from((300, 200), (100, 150)) == (100, 150, 200, 50)
    assert box_from((10, 10), (11, 40)) is None
