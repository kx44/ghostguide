import re
from pathlib import Path

import pytest

from engine.schema import messages as m

TS = Path("overlay/shared/messages.ts")


def test_parse_overlay_messages():
    assert m.parse_from_overlay('{"type":"next"}').type == "next"
    assert m.parse_from_overlay({"type": "jump", "n": 4}).n == 4
    h = m.parse_from_overlay({"type": "hello", "displays": [{"id": 0, "x": 0, "y": 0, "w": 10, "h": 10}]})
    assert h.displays[0].w == 10
    for bad in ('{"type":"nope"}', "not json", '{"type":"jump"}', '{"type":"next","extra":1}'):
        with pytest.raises(ValueError):
            m.parse_from_overlay(bad)


def test_types_mirrored_in_typescript():
    ts = TS.read_text(encoding="utf-8")
    styles = re.search(r"export const STYLES = \[(.*?)\] as const", ts, re.S).group(1)
    assert re.findall(r'"(\w+)"', styles) == list(m.STYLES)
    to_ov = re.search(r"export const TO_OVERLAY = \[(.*?)\] as const", ts, re.S).group(1)
    assert re.findall(r'"(\w+)"', to_ov) == list(m.TO_OVERLAY_TYPES)
    from_ov = re.search(r"export const FROM_OVERLAY = \[(.*?)\] as const", ts, re.S).group(1)
    assert re.findall(r'"(\w+)"', from_ov) == list(m.FROM_OVERLAY_TYPES)
