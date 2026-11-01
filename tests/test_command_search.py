"""When nothing can point at a control, the card falls back on the app's own command search. Words only: nothing is pressed."""
from engine import config
from engine.appmap.store import SEARCH_ENTRY, AppMapStore
from engine.compile.enrich import clean_search, look_up_search
from engine.live.locate.menu import search_hint
from engine.live.locate.resolver import Resolver
from engine.live.player import Player
from engine.live.session import Session
from engine.models.client import ModelError
from engine.schema.appmap import Control
from engine.schema.tutorial import Source, SourceInfo, Step, Target, Tutorial, TutorialMeta


class Store:
    def __init__(self, search=None):
        self.search = search

    def command_search(self):
        return self.search

    def get(self, label):
        return None


def step(action="click", label="Front", kind="button", **target):
    return Step(n=1, title="One", action=action, target=Target(label=label, kind=kind, **target), check="c", source=Source(anchor="#a"))


PALETTE = Control(aliases=["Command Palette"], shortcut="Ctrl+Shift+P")


class NoUia:
    window = "App"
    last_how = "not found"
    last_extra: dict = {}

    def locate(self, s, label=None):
        return None, None


class Vision:
    last_how, last_conf, last_line, last_route = "vision", "", None, None

    def __init__(self, spent):
        self.is_spent = spent

    def find(self, s, label=None, **kw):
        return None

    def spent(self, n, label):
        return self.is_spent


def test_the_hint_says_what_to_press_and_type():
    assert search_hint(Store(PALETTE), "Save") == "Use Command Palette: press Ctrl+Shift+P and type Save."
    box = Control(aliases=["Search Commands"], where="Hover the result.")
    assert search_hint(Store(box), "Line ▾") == "Use Search Commands: type Line. Hover the result."
    assert search_hint(Store(PALETTE), "Front (view)") .endswith("type Front.")


def test_no_search_or_a_dialogs_own_button_gives_no_hint():
    assert search_hint(Store(), "Save") is None
    assert search_hint(object(), "Save") is None
    assert search_hint(None, "Save") is None
    assert search_hint(Store(PALETTE), "OK (green check)") is None


def test_the_finder_offers_it_only_once_nothing_else_can():
    r = Resolver(NoUia(), Store(PALETTE))
    assert r.locate(step()) == (None, None)
    assert "Command Palette" in r.last_extra["search"]
    r = Resolver(NoUia(), Store(PALETTE), vision=Vision(spent=False))      # sight still has looks left
    r.locate(step())
    assert "search" not in r.last_extra
    r = Resolver(NoUia(), Store(PALETTE), vision=Vision(spent=True))
    r.locate(step())
    assert "search" in r.last_extra


def test_only_what_a_command_search_can_find():
    for s in (step(kind="canvas"), step(kind="field"), step(action="shortcut"), step(action="look"), step(action="switch_app", kind="window")):
        r = Resolver(NoUia(), Store(PALETTE))
        r.locate(s)
        assert "search" not in r.last_extra


def test_the_card_adds_it_to_what_it_already_says():
    class Locator:
        last_how, last_stage = "not found", "none"
        last_extra = {"search": "Use Command Palette: press Ctrl+Shift+P and type Front."}

        def locate(self, s):
            return None, None

    tut = Tutorial(meta=TutorialMeta(title="T", app="App", source=SourceInfo(type="text")), steps=[step()])
    p = Player(Session(tut), locator=Locator())
    g = [x for x in p.apply_located(p.locate_current()) if x.type == "guide"][0]
    assert g.card.detail.endswith("Can't point at it. Use Command Palette: press Ctrl+Shift+P and type Front.")
    assert g.card.dev_hint is None
    assert "do_it" not in g.card.actions


def test_a_lookup_needs_a_page_and_stays_short_and_plain():
    assert clean_search({"name": "Palette", "keys": "F1", "how": "x", "source": "https://a"}) == \
        {"aliases": ["Palette"], "source": "https://a", "shortcut": "F1", "where": "x"}
    assert clean_search({"name": "Palette", "source": "not a link"}) is None
    assert clean_search({"name": "x" * 41, "source": "https://a"}) is None
    assert clean_search({}) is None and clean_search([]) is None
    assert "shortcut" not in clean_search({"name": "P", "keys": "<script>; rm -rf", "source": "https://a"})
    assert "where" not in clean_search({"name": "P", "how": "x" * 161, "source": "https://a"})
    assert clean_search({"none": True}) == {"source": "looked up, none found"}


class Reply:
    searches = 1

    def __init__(self, text):
        self.text = text


class Client:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    def respond(self, model, text, **kw):
        self.calls += 1
        assert kw["tools"] == [{"type": "web_search"}] and model == config.SPARK_CONTRIBUTOR
        if isinstance(self.text, Exception):
            raise self.text
        return Reply(self.text)


def _store(tmp_path):
    return AppMapStore("Some Tool", builtin_dir=tmp_path / "none", local=tmp_path)


def test_each_app_is_looked_up_once(tmp_path):
    c = Client('{"name": "Finder", "keys": "F3", "source": "https://a"}')
    s = _store(tmp_path)
    assert look_up_search(c,"Some Tool", s)
    assert s.command_search().aliases == ["Finder"] and s.command_search().shortcut == "F3"
    assert not look_up_search(c,"Some Tool", _store(tmp_path))       # from the saved map
    assert c.calls == 1


def test_an_app_with_none_isnt_paid_for_twice_and_a_failure_is_tried_again(tmp_path):
    c = Client('{"none": true}')
    s = _store(tmp_path)
    assert look_up_search(c,"Some Tool", s)
    assert s.command_search() is None and s.get(SEARCH_ENTRY) is not None
    assert not look_up_search(c,"Some Tool", s) and c.calls == 1
    other = AppMapStore("Other Tool", builtin_dir=tmp_path / "none", local=tmp_path)
    assert not look_up_search(Client(ModelError("down")),"Other Tool", other)
    assert not look_up_search(Client("not json"),"Other Tool", other)
    assert other.get(SEARCH_ENTRY) is None


def test_the_built_in_maps_have_it():
    assert AppMapStore("VS Code").command_search().aliases == ["Command Palette"]
    assert AppMapStore("SOLIDWORKS", "2026").command_search().shortcut == "W"
