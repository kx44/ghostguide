"""Finder chain (locate/resolver.py) and the two-layer app map (appmap/store.py)."""
from pathlib import Path

import yaml

from engine.appmap.store import AppMapStore, pick_file, slug, version_pattern
from engine.basefile.parse import parse_file
from engine.live.locate import menu
from engine.live.locate.appmap_hit import learnable, place
from engine.live.locate.resolver import GenericUIA, Resolver
from engine.live.locate.vision import to_screen
from engine.models.tools import PointAt
from engine.schema.messages import Box

ROOT = Path(__file__).resolve().parent.parent
VS = parse_file(ROOT / "tutorials/youtube-clone-vscode.md")
MUG = parse_file(ROOT / "tutorials/mug-solidworks.md")
WIN = (100, 50, 1000, 800)


def store(tmp_path, builtin=None, version="1.143.1"):
    b = tmp_path / "builtin"
    b.mkdir(exist_ok=True)
    if builtin is not None:
        (b / "vscode-1.14x.yaml").write_text(yaml.safe_dump(builtin), encoding="utf-8")
    return AppMapStore("Visual Studio Code", version=version, builtin_dir=b, local=tmp_path / "local")


# ---------- app map store ----------
def test_file_per_version_pattern(tmp_path):
    for n in ("vscode-1.12x.yaml", "vscode-1.14x.yaml", "solidworks-2026.yaml"):
        (tmp_path / n).write_text("{}", encoding="utf-8")
    assert pick_file(tmp_path, "vscode", "1.143.1").name == "vscode-1.14x.yaml"
    assert pick_file(tmp_path, "vscode", "1.125.0").name == "vscode-1.12x.yaml"
    assert pick_file(tmp_path, "vscode", "1.990").name == "vscode-1.14x.yaml"      # unknown: newest
    assert pick_file(tmp_path, "blender", None) is None
    assert slug("Visual Studio Code") == "vscode" and slug("SOLIDWORKS 2026") == "solidworks"
    assert version_pattern("1.143.1") == "1.14x"


def test_local_read_first_builtin_never_written(tmp_path):
    st = store(tmp_path, {"Save": {"shortcut": "Ctrl+S", "menu_path": ["File", "Save"]}})
    before = st.builtin_path.read_text(encoding="utf-8")
    assert st.get("Save").shortcut == "Ctrl+S"
    assert st.learn("Save", "youtube-clone - Visual Studio Code", (200, 90, 20, 10), WIN)
    st.add_facts("Save", aliases=["Save File"])
    again = store(tmp_path)
    c = again.get("Save")
    assert c.shortcut == "Ctrl+S" and c.aliases == ["Save File"]                   # both layers, merged
    assert c.seen.rel_box == (0.1, 0.05, 0.02, 0.0125)
    assert st.builtin_path.read_text(encoding="utf-8") == before                   # writes go local only


def test_learn_refuses_a_box_outside_its_window(tmp_path):
    st = store(tmp_path)
    assert not st.learn("Save", "w", (50, 90, 20, 10), WIN)
    assert st.get("Save") is None


def test_promote_copies_docs_facts_never_positions(tmp_path):
    st = store(tmp_path)
    st.add_facts("New File...", aliases=["New File"], source="code.visualstudio.com/docs")
    st.learn("New File...", "w", (200, 90, 20, 10), WIN)
    assert st.reviewable() == {"New File...": {"aliases": ["New File"], "source": "code.visualstudio.com/docs"}}
    path = st.promote(list(st.reviewable()))
    assert path.name == "vscode-1.14x.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert data == {"New File...": {"aliases": ["New File"], "source": "code.visualstudio.com/docs"}}
    assert store(tmp_path).reviewable() == {}


def test_the_shipped_vscode_map_is_docs_facts_only():
    st = AppMapStore("Visual Studio Code", version="1.143.1", local=Path("/nonexistent"))
    assert st.builtin_path is not None and st.builtin_path.name == "vscode-1.14x.yaml"
    assert st.builtin.root and not st.builtin.has_positions
    assert all(c.source for c in st.builtin.root.values())


# ---------- stages ----------
def test_remembered_boxes_only_for_controls_that_stay_put():
    assert learnable(VS.step(1))                      # New File button
    assert not learnable(VS.step(2))                  # filename box
    assert not learnable(VS.step(14))                 # a tab moves as tabs open
    assert place((0.1, 0.05, 0.02, 0.0125), WIN) == Box(x=200, y=90, w=20, h=10)


class Stage:
    window = "W"

    def __init__(self, box=None):
        self.box, self.last_how, self.last_extra = box, "", {}

    def locate(self, step):
        self.last_how = "named control" if self.box else "not found"
        return self.box, None


def test_resolver_order_uia_then_remembered_then_vision_then_route(tmp_path):
    st = store(tmp_path, {"New File...": {"menu_path": ["File", "New File..."], "source": "docs"}})
    st.learn("New File...", "W", (200, 90, 20, 10), WIN)
    step = VS.step(12)                                # label "New File..."
    r = Resolver(Stage(Box(x=1, y=2, w=3, h=4)), st, lambda part: WIN)
    assert r.locate(step)[0] == Box(x=1, y=2, w=3, h=4) and r.last_stage == "uia"
    r = Resolver(Stage(None), st, lambda part: WIN)
    assert r.locate(step)[0] == Box(x=200, y=90, w=20, h=10) and r.last_stage == "appmap"
    r = Resolver(Stage(None), st, lambda part: None)                   # window gone: no remembered box

    class Vision:
        last_how = "vision: Spark pointed (high)"

        def find(self, step):
            return Box(x=9, y=9, w=9, h=9)
    assert r.locate(step) == (None, None) and r.last_stage == "route"
    assert r.last_extra["route"] == {"path": ["File", "New File..."]} and "Route: File › New File..." in r.last_how
    r.vision = Vision()
    assert r.locate(step)[0] == Box(x=9, y=9, w=9, h=9) and r.last_stage == "vision"


def test_resolver_learns_after_a_checked_step(tmp_path):
    st = store(tmp_path)
    r = Resolver(Stage(), st, lambda part: WIN)
    assert r.learn(VS.step(1), Box(x=200, y=90, w=20, h=10))
    assert not r.learn(VS.step(2), Box(x=200, y=90, w=20, h=10))
    assert st.get("New File").seen is not None


def test_generic_uia_uses_aliases_from_the_app_map(tmp_path):
    st = AppMapStore("SOLIDWORKS", builtin_dir=tmp_path, local=tmp_path / "l")
    st.add_facts("Extruded Cut", aliases=["Extrude Cut"])
    els = [{"name": "Extrude Cut", "type": "Button", "rect": [10, 10, 30, 30]},
           {"name": "Extruded Boss", "type": "Button", "rect": [50, 10, 30, 30]}]
    g = GenericUIA("SOLIDWORKS", st, dump=lambda w: els)
    step = VS.step(1).model_copy(update={"target": VS.step(1).target.model_copy(update={"label": "Extruded Cut"})})
    box, _ = g.locate(step)
    assert box == Box(x=10, y=10, w=30, h=30) and g.last_how == "alias 'Extrude Cut'"


def test_route_and_vision_mapping():
    assert menu.route(VS.step(7)) == {"path": ["index.html (right-click)", "Open with Live Server"], "shortcut": "Alt+L Alt+O"}
    assert menu.route(VS.step(2)) is None
    assert to_screen(PointAt(x=64, y=32, w=10, h=10, confidence="high"), 0.5, (100, 50)) == Box(x=218, y=104, w=20, h=20)
