import pytest
from pydantic import ValidationError

from engine.schema.appmap import AppMap

DOC = {
    "Extruded Cut": {"aliases": ["Extrude Cut", "Cut-Extrude"], "menu_path": ["Insert", "Cut", "Extrude"],
                     "shortcut": None, "source": "help.solidworks.com/2026/x"},
}


def test_lookup_by_label_and_alias(tmp_path):
    m = AppMap.model_validate(DOC)
    assert m.get("Extruded Cut").menu_path == ["Insert", "Cut", "Extrude"]
    assert m.get("Cut-Extrude") is m.get("Extruded Cut")
    assert m.get("Fillet") is None and not m.has_positions
    p = tmp_path / "sw.yaml"
    m.dump(p)
    assert AppMap.load(p) == m


def test_local_layer_positions_are_window_relative():
    local = {"Extruded Cut": {"seen": {"window": "SOLIDWORKS", "rel_box": [0.31, 0.06, 0.03, 0.05]}}}
    assert AppMap.model_validate(local).has_positions
    with pytest.raises(ValidationError):
        AppMap.model_validate({"X": {"seen": {"window": "W", "rel_box": [310, 60, 30, 50]}}})
