import json

import pytest

from engine import config
from engine.models.cassette import CassetteMiss, request_key
from engine.models.client import BudgetExceeded, ModelClient, estimate_cost, image_part, parse_response, text_part
from engine.models.tools import LOCATE_TOOLS, MenuPath, PointAt

OPENAI_REPLY = {
    "choices": [{"message": {"content": "GhostGuide ready.", "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "point_at", "arguments": json.dumps(
            {"x": 10, "y": 20, "w": 30, "h": 40, "confidence": "high", "label_seen": "Extruded Cut"})}}]}}],
    "usage": {"prompt_tokens": 1000, "completion_tokens": 100},
}
LLAMA_REPLY = {
    "completion_message": {"content": {"type": "text", "text": "ok"}, "tool_calls": [
        {"id": "c2", "function": {"name": "menu_path", "arguments": '{"path": ["Insert", "Cut", "Extrude"], "confidence": "low"}'}}]},
    "metrics": [{"metric": "num_prompt_tokens", "value": 50}, {"metric": "num_completion_tokens", "value": 5}],
}
MSG = [{"role": "user", "content": "Reply with exactly: GhostGuide ready."}]


class FakeAPI:
    def __init__(self, reply=OPENAI_REPLY):
        self.calls = 0
        self.reply = reply

    def __call__(self, request):
        self.calls += 1
        return self.reply


def client(tmp_path, mode, api=None, budget=4.0):
    return ModelClient(mode=mode, budget_usd=budget, cassette_dir=tmp_path / "cassettes",
                       cost_log=tmp_path / "costs.jsonl", transport=api or FakeAPI())


def test_default_mode_is_replay(monkeypatch):
    monkeypatch.delenv("MODEL_MODE", raising=False)
    monkeypatch.delenv("BUDGET_USD", raising=False)
    assert config.model_mode() == "replay"
    assert config.budget_usd() == 4.0


def test_replay_without_recording_never_calls_the_api(tmp_path):
    api = FakeAPI()
    with pytest.raises(CassetteMiss, match="MODEL_MODE=record"):
        client(tmp_path, "replay", api).chat(config.SPARK, MSG, max_tokens=16)
    assert api.calls == 0


def test_record_then_replay_offline(tmp_path):
    api = FakeAPI()
    rec = client(tmp_path, "record", api).chat(config.SPARK, MSG, max_tokens=16, tools=LOCATE_TOOLS, tag="t")
    assert api.calls == 1 and not rec.from_cassette
    assert rec.cost_usd == pytest.approx((1000 * 1.25 + 100 * 4.25) / 1e6)
    assert rec.tool_calls == [PointAt(x=10, y=20, w=30, h=40, confidence="high", label_seen="Extruded Cut")]

    offline = FakeAPI()
    rep = client(tmp_path, "replay", offline).chat(config.SPARK, MSG, max_tokens=16, tools=LOCATE_TOOLS)
    assert offline.calls == 0 and rep.from_cassette and rep.cost_usd == 0
    assert rep.text == "GhostGuide ready." and rep.tool_calls == rec.tool_calls

    # record mode reuses what is recorded instead of paying again
    again = client(tmp_path, "record", api).chat(config.SPARK, MSG, max_tokens=16, tools=LOCATE_TOOLS)
    assert api.calls == 1 and again.from_cassette


def test_live_logs_cost_but_saves_nothing(tmp_path):
    c = client(tmp_path, "live")
    c.chat(config.SPARK, MSG, max_tokens=16)
    c.chat(config.SPARK, MSG, max_tokens=16)
    assert not (tmp_path / "cassettes").exists()
    lines = (tmp_path / "costs.jsonl").read_text().splitlines()
    assert len(lines) == 2 and json.loads(lines[0])["model"] == config.SPARK
    assert c.spent_usd() == pytest.approx(2 * (1000 * 1.25 + 100 * 4.25) / 1e6)


def test_budget_cap_refuses_before_calling(tmp_path):
    (tmp_path / "costs.jsonl").write_text(json.dumps({"cost_usd": 3.999}) + "\n")
    api = FakeAPI()
    c = client(tmp_path, "live", api)
    with pytest.raises(BudgetExceeded, match=r"\$4.00 budget"):
        c.chat(config.WONDER, MSG, max_tokens=1000)     # worst case $0.02 > $0.001 left
    assert api.calls == 0
    c.chat(config.SPARK_CONTRIBUTOR, MSG, max_tokens=16)  # tiny call still fits
    assert api.calls == 1


def test_budget_counts_previous_runs(tmp_path):
    big = {**OPENAI_REPLY, "usage": {"prompt_tokens": 0, "completion_tokens": 200_000}}  # $0.85 each
    c = client(tmp_path, "live", FakeAPI(big), budget=2.0)
    c.chat(config.SPARK, MSG, max_tokens=8000)
    c.chat(config.SPARK, MSG, max_tokens=8000)
    fresh = client(tmp_path, "live", FakeAPI(big), budget=2.0)   # new process, same log
    assert fresh.spent_usd() == pytest.approx(1.70)
    with pytest.raises(BudgetExceeded):
        fresh.chat(config.SPARK, [{"role": "user", "content": "x" * 900_000}], max_tokens=8000)


def test_missing_usage_logs_the_estimate(tmp_path):
    c = client(tmp_path, "live", FakeAPI({"choices": [{"message": {"content": "hi"}}]}))
    r = c.chat(config.SPARK, MSG, max_tokens=100)
    assert r.cost_usd > 0 and c.spent_usd() == pytest.approx(r.cost_usd)


def test_unknown_model_is_refused_live_but_replays(tmp_path):
    with pytest.raises(BudgetExceeded, match="no price"):
        client(tmp_path, "live").chat("muse-mystery", MSG, max_tokens=16)


def test_estimate_counts_images_and_web_search():
    png = b"\x89PNG" + b"0" * 5000
    base = {"model": config.SPARK, "messages": [{"role": "user", "content": [text_part("find it")]}], "max_tokens": 100}
    with_img = {**base, "messages": [{"role": "user", "content": [text_part("find it"), image_part(png)]}]}
    assert estimate_cost(with_img) - estimate_cost(base) == pytest.approx(3000 * 1.25 / 1e6)
    assert estimate_cost({**base, "tools": [{"type": "web_search"}]}) > estimate_cost(base) + 0.04


def test_image_keys_are_stable_and_by_content():
    a = {"model": "m", "messages": [{"role": "user", "content": [image_part(b"one")]}], "max_tokens": 1}
    b = {"model": "m", "messages": [{"role": "user", "content": [image_part(b"two")]}], "max_tokens": 1}
    assert request_key(a) == request_key(json.loads(json.dumps(a)))
    assert request_key(a) != request_key(b)


def test_guards(tmp_path):
    c = client(tmp_path, "live")
    with pytest.raises(ValueError, match="max_tokens"):
        c.chat(config.SPARK, MSG, max_tokens=100_000)
    many = [{"role": "user", "content": [image_part(bytes([i])) for i in range(51)]}]
    with pytest.raises(ValueError, match="50 images"):
        c.chat(config.SPARK, many, max_tokens=10)


def test_parses_llama_style_replies():
    text, calls, usage = parse_response(LLAMA_REPLY)
    assert text == "ok" and calls[0]["name"] == "menu_path"
    assert (usage.input_tokens, usage.output_tokens) == (50, 5)


def test_llama_tool_calls_become_typed(tmp_path):
    r = client(tmp_path, "live", FakeAPI(LLAMA_REPLY)).chat(config.SPARK, MSG, max_tokens=16)
    assert r.tool_calls == [MenuPath(path=["Insert", "Cut", "Extrude"], confidence="low")]


def test_cli_record_replays_offline(tmp_path, monkeypatch, capsys):
    from engine import cli
    from engine.models import client as client_mod

    monkeypatch.setattr(config, "CASSETTES", tmp_path / "cassettes")
    monkeypatch.setattr(config, "COST_LOG", tmp_path / "costs.jsonl")
    monkeypatch.setattr(client_mod, "_http_send", lambda request, **kw: OPENAI_REPLY)
    assert cli.main(["record", "--mode", "record"]) == 0
    monkeypatch.setattr(client_mod, "_http_send", lambda request, **kw: pytest.fail("network used in replay"))
    assert cli.main(["record", "--mode", "replay"]) == 0
    assert "cached=True" in capsys.readouterr().out
