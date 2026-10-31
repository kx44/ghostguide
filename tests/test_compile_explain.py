"""The explain pass with a fake transport: it fills empty `why` fields and touches nothing else, and it can't stop a compile."""
import copy
import json

import pytest

from engine.basefile.parse import parse_file
from engine.compile.passes.explain import LONG_MAX_WORDS, MAX_WORDS, SCHEMA, _frozen, explain
from engine.compile.pipeline import Options, compile_tutorial
from engine.models.client import BudgetExceeded, ModelClient, ModelError
from engine.schema.tutorial import Step, Tutorial, TutorialMeta

MODEL = "muse-spark-1.3"
GOOD = "Gives the page a title, so people can tell what it is."


def _step(n, action="type", why=None, value="x = 1", **extra):
    params = {"value": value} if action == "type" and value is not None else {}
    return Step(n=n, title=f"Step {n}", action=action, target={"label": "Editor" if action == "type" else f"Control {n}", "kind": "field" if action == "type" else "button"},
                params=params, why=why, check=f"Check {n}", source={"t": "00:01"}, confidence="high", **extra)


def _tut(*steps):
    return Tutorial(meta=TutorialMeta(title="T", app="A", source={"type": "text"}), steps=list(steps))


def _reply(text):
    return {"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 100, "completion_tokens": 50}}


def _lines(*pairs, **extra):
    return json.dumps({"explanations": [{"n": n, "why": w} for n, w in pairs], **extra})


class Api:
    """Answers each call in turn; an exception in the list is raised."""

    def __init__(self, *answers):
        self.answers, self.requests = list(answers), []

    def __call__(self, request):
        self.requests.append(request)
        a = self.answers.pop(0)
        if isinstance(a, Exception):
            raise a
        return _reply(a)


def _client(tmp_path, api, budget=5.0):
    return ModelClient(mode="record", budget_usd=budget, cassette_dir=tmp_path / "c", cost_log=tmp_path / "costs.jsonl", transport=api)


def test_only_empty_whys_get_filled(tmp_path):
    tut = _tut(_step(1), _step(2, why="Already said."), _step(3, "click"))
    api = Api(_lines((1, GOOD), (2, "A different line."), (3, "Opens the panel the next step needs.")))
    info = explain(_client(tmp_path, api), MODEL, tut)
    assert [s.why for s in tut.steps] == [GOOD, "Already said.", "Opens the panel the next step needs."]
    assert info["filled"] == 1 and info["filled_optional"] == 1 and not info["warnings"]
    assert len(api.requests) == 1


def test_suggested_values_count_as_typed(tmp_path):
    tut = _tut(_step(1, value=None))
    tut.steps[0].params["suggested"] = {"value": "5", "note": "any small value"}
    api = Api(_lines((1, "Sets how far the part sticks out.")))
    assert explain(_client(tmp_path, api), MODEL, tut)["asked"] == 1
    assert tut.steps[0].why == "Sets how far the part sticks out."
    assert '"text": "5"' in api.requests[0]["messages"][1]["content"]


def test_a_reply_cannot_touch_anything_else(tmp_path):
    tut = _tut(_step(1), _step(2, "click"), _step(3))
    before = copy.deepcopy(_frozen(tut))
    evil = json.dumps({"steps": [], "title": "Hacked", "explanations": [
        {"n": 3, "why": GOOD, "title": "Hacked", "action": "click", "params": {"value": "rm -rf"}},
        {"n": 1, "why": GOOD}, {"n": 99, "why": "No such step."}, {"n": "2", "why": "Wrong type."}, {"n": True, "why": "Not a number."}]})
    explain(_client(tmp_path, Api(evil)), MODEL, tut)
    assert _frozen(tut) == before and len(tut.steps) == 3 and tut.meta.title == "T"
    assert [s.n for s in tut.steps] == [1, 2, 3] and tut.steps[0].why == tut.steps[2].why == GOOD and tut.steps[1].why is None


def test_steps_changed_by_the_pass_lose_their_lines(tmp_path, monkeypatch):
    from engine.compile.passes import explain as ex
    real = ex.fill

    def bad_fill(tut, lines):
        tut.steps[0].title = "Changed"
        return real(tut, lines)

    monkeypatch.setattr(ex, "fill", bad_fill)
    tut = _tut(_step(1))
    info = ex.explain(_client(tmp_path, Api(_lines((1, GOOD)))), MODEL, tut)
    assert tut.steps[0].why is None and info["filled"] == 0 and "dropped" in info["warnings"][0]


def test_repeat_clicks_are_not_offered_their_small_card_shows_no_line(tmp_path):
    tut = _tut(_step(1, "click"), _step(2, "click", repeat_of=1))
    explain(_client(tmp_path, Api(_lines((1, "Fine reason."), (2, "Never shown.")))), MODEL, tut)
    assert tut.steps[0].why == "Fine reason." and tut.steps[1].why is None


def test_too_long_is_asked_again_and_never_cut(tmp_path):
    long_line = " ".join(["word"] * (MAX_WORDS + 1))
    tut = _tut(_step(1))
    api = Api(_lines((1, long_line)), _lines((1, GOOD)))
    assert not explain(_client(tmp_path, api), MODEL, tut)["warnings"]
    assert tut.steps[0].why == GOOD
    assert "too long" in api.requests[1]["messages"][-1]["content"]


def test_too_long_twice_leaves_it_empty_and_warns(tmp_path):
    long_line = " ".join(["word"] * (MAX_WORDS + 1))
    tut = _tut(_step(1))
    info = explain(_client(tmp_path, Api(_lines((1, long_line)), _lines((1, long_line)))), MODEL, tut)
    assert tut.steps[0].why is None and info["filled"] == 0 and "step 1" in info["warnings"][0]


def test_a_long_block_gets_more_room_but_still_a_limit(tmp_path):
    block = "\n".join(f"line {i}" for i in range(6))
    fits, over = " ".join(["w"] * LONG_MAX_WORDS), " ".join(["w"] * (LONG_MAX_WORDS + 1))
    tut = _tut(_step(1, value=block), _step(2, value=block))
    explain(_client(tmp_path, Api(_lines((1, fits), (2, over)), _lines())), MODEL, tut)
    assert tut.steps[0].why == fits and tut.steps[1].why is None


def test_a_line_that_only_repeats_the_step_is_refused(tmp_path):
    tut = _tut(_step(1))
    api = Api(_lines((1, "Step 1.")), _lines((1, GOOD)))
    explain(_client(tmp_path, api), MODEL, tut)
    assert tut.steps[0].why == GOOD and "repeats" in api.requests[1]["messages"][-1]["content"]


def test_line_breaks_become_one_line(tmp_path):
    tut = _tut(_step(1))
    explain(_client(tmp_path, Api(_lines((1, "One line\n  and another.")))), MODEL, tut)
    assert tut.steps[0].why == "One line and another."


@pytest.mark.parametrize("bad", ["not json", "[1, 2]", '{"explanations": "none"}', '{"explanations": [1, null, {}]}', ""])
def test_malformed_replies_warn_and_change_nothing(tmp_path, bad):
    tut = _tut(_step(1))
    info = explain(_client(tmp_path, Api(bad, bad)), MODEL, tut)
    assert tut.steps[0].why is None and info["warnings"]


@pytest.mark.parametrize("error", [ModelError("500"), BudgetExceeded("cap"), RuntimeError("anything"), KeyError("x")])
def test_a_failed_call_is_only_a_warning(tmp_path, error):
    tut = _tut(_step(1))
    info = explain(_client(tmp_path, Api(error)), MODEL, tut)
    assert tut.steps[0].why is None and "stopped early" in info["warnings"][0]


def test_a_second_try_failing_keeps_the_first_tries_lines(tmp_path):
    tut = _tut(_step(1), _step(2))
    info = explain(_client(tmp_path, Api(_lines((1, GOOD)), ModelError("500"))), MODEL, tut)
    assert tut.steps[0].why == GOOD and tut.steps[1].why is None and info["filled"] == 1 and len(info["warnings"]) == 2


def test_the_budget_cap_applies(tmp_path):
    tut = _tut(_step(1))
    info = explain(_client(tmp_path, Api(_lines((1, GOOD))), budget=0.0001), MODEL, tut)
    assert "BudgetExceeded" in info["warnings"][0]


def test_nothing_to_explain_makes_no_call(tmp_path):
    api = Api()
    assert explain(_client(tmp_path, api), MODEL, _tut(_step(1, why="Said."))) == {"asked": 0, "filled": 0, "filled_optional": 0, "warnings": []}
    assert not api.requests


def test_the_request_is_structured_low_effort_and_replays_free(tmp_path):
    api = Api(_lines((1, GOOD)))
    client = _client(tmp_path, api)
    explain(client, MODEL, _tut(_step(1)))
    r = api.requests[0]
    assert r["reasoning_effort"] == "low" and r["model"] == MODEL and r["response_format"]["json_schema"] is SCHEMA
    item = SCHEMA["schema"]["properties"]["explanations"]["items"]
    assert SCHEMA["schema"]["additionalProperties"] is False and item["additionalProperties"] is False
    assert set(item["properties"]) == {"n", "why"}
    spent = client.spent_usd()
    tut = _tut(_step(1))
    explain(client, MODEL, tut)
    assert tut.steps[0].why == GOOD and client.spent_usd() == spent and len(api.requests) == 1


# ---- in the pipeline ----
RAW = json.dumps({"setup": [], "actions": [{"action": "type", "label": "Editor", "kind": "field", "at": "#s", "evidence": "said", "value": "x = 1"}]})
DRAFT = {"title": "T", "app": "A", "steps": [{"title": "Type it", "action": "type", "target": {"label": "Editor", "kind": "field"},
                                             "params": {"value": "x = 1"}, "check": "x shows", "source": {"anchor": "#s"}, "confidence": "high"}]}


def _compile(tmp_path, monkeypatch, explain_answer):
    from engine.compile import pipeline as pl
    monkeypatch.setattr(pl, "CACHE", tmp_path / "compiled")
    monkeypatch.setattr(pl, "SCORES", tmp_path / "scores.jsonl")
    monkeypatch.setenv("GG_LOCAL_APPMAPS", str(tmp_path / "maps"))
    calls = []

    def api(request):
        name = request["response_format"]["json_schema"]["name"]
        calls.append(name)
        if name == "explanations":
            if isinstance(explain_answer, Exception):
                raise explain_answer
            return _reply(explain_answer)
        return _reply(RAW if name == "raw_actions" else json.dumps(DRAFT))

    source = tmp_path / "t.txt"
    source.write_text("# Start\nType x = 1.\n", encoding="utf-8")
    opts = Options(out=tmp_path / "out" / "t.compiled.md", model=MODEL, enrich=False)
    client = _client(tmp_path, api)
    return compile_tutorial(str(source), opts, client=client), parse_file(opts.out), source, opts, client, calls


def test_compile_saves_the_line(tmp_path, monkeypatch):
    r, saved, *_ = _compile(tmp_path, monkeypatch, _lines((1, GOOD)))
    assert saved.steps[0].why == GOOD and not r.warnings


@pytest.mark.parametrize("answer", [ModelError("500"), "not json", _lines((1, "w " * 99))])
def test_compile_still_saves_with_a_warning_and_tries_again_next_time(tmp_path, monkeypatch, answer):
    r, saved, source, opts, client, calls = _compile(tmp_path, monkeypatch, answer)
    assert r.steps == 1 and r.path.exists() and saved.steps[0].why is None and saved.steps[0].params["value"] == "x = 1"
    assert r.warnings
    assert not compile_tutorial(str(source), opts, client=client).cached
