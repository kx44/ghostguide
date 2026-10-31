"""The one door to the Meta models: record/replay, cost log and a local budget cap.

Modes (MODEL_MODE, default `replay`):
- replay: answers only from cache/cassettes/; never touches the network, costs nothing.
- record: replays what is already recorded, calls the API for anything new and saves it.
- live:   always calls the API, saves nothing.

Budget: Meta has no hard spend cap, so every live/record call is checked first. The client estimates
the call's worst case (input from the request size, output = max_tokens) and refuses it if the logged
spend plus that estimate would pass BUDGET_USD (default $4). Actual cost is logged from the response's
usage to cache/logs/costs.jsonl, which is the running total across runs.

Wire format: OpenAI-style chat completions at https://api.meta.ai/v1/chat/completions (dev.meta.ai docs,
confirmed 31 Oct). The parser also reads Llama-API-style replies (`completion_message`, `metrics`).
Muse Spark always reasons and the reasoning counts toward max_tokens, so short answers need
`reasoning_effort` ("minimal" / "low") and some headroom in max_tokens, or the reply can come back empty.
"""
from __future__ import annotations

import base64
import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from engine import config
from engine.models.cassette import Cassettes, request_key
from engine.models.tools import ToolCall, parse_tool_call

# Rough tokens per image for the pre-call estimate. Deliberately high so the cap errs on the safe side.
IMAGE_TOKENS_ESTIMATE = 3000
CHARS_PER_TOKEN = 3
# web_search pricing is unconfirmed (04 Base format, open items); reserve this much per call that offers it.
WEB_SEARCH_RESERVE_USD = 0.05
MAX_TOKENS_CEILING = 8192


class BudgetExceeded(RuntimeError):
    pass


class ModelError(RuntimeError):
    pass


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class Reply:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_tool_calls: list[dict] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    cost_usd: float = 0.0
    from_cassette: bool = False
    cassette_key: str = ""
    raw: dict = field(default_factory=dict)


def image_part(png: bytes, mime: str = "image/png") -> dict:
    """A message content part carrying one screenshot or frame."""
    return {"type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{base64.b64encode(png).decode()}"}}


def text_part(text: str) -> dict:
    return {"type": "text", "text": text}


def price(model: str) -> tuple[float, float]:
    if model not in config.PRICES:
        raise BudgetExceeded(f"no price known for {model!r}; add it to config.PRICES before calling it live")
    return config.PRICES[model]


def cost_of(model: str, usage: Usage) -> float:
    p_in, p_out = price(model)
    return (usage.input_tokens * p_in + usage.output_tokens * p_out) / 1_000_000


def _count_images(messages: list[dict]) -> int:
    n = 0
    for m in messages:
        content = m.get("content")
        if isinstance(content, list):
            n += sum(1 for part in content if isinstance(part, dict) and part.get("type") in ("image_url", "image"))
    return n


def estimate_cost(request: dict) -> float:
    """Worst case for one call: every text char ~1/3 token, each image a fixed allowance, full max_tokens out."""
    model = request["model"]
    p_in, p_out = price(model)
    images = _count_images(request["messages"])
    text_chars = len(json.dumps(
        [{**m, "content": [p for p in m["content"] if p.get("type") == "text"]} if isinstance(m.get("content"), list) else m
         for m in request["messages"]]))
    text_chars += len(json.dumps(request.get("tools") or []))
    in_tokens = text_chars / CHARS_PER_TOKEN + images * IMAGE_TOKENS_ESTIMATE
    usd = (in_tokens * p_in + request["max_tokens"] * p_out) / 1_000_000
    if any(t.get("type") == "web_search" for t in request.get("tools") or []):
        usd += WEB_SEARCH_RESERVE_USD
    return usd


def parse_response(data: dict) -> tuple[str, list[dict], Usage]:
    """Text, raw tool calls [{name, arguments}], usage — from OpenAI-style or Llama-API-style replies."""
    text, calls = "", []
    if "choices" in data:
        msg = data["choices"][0].get("message", {})
        content = msg.get("content")
        if isinstance(content, list):
            text = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        else:
            text = content or ""
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", tc)
            calls.append({"id": tc.get("id"), "name": fn["name"], "arguments": fn.get("arguments", "{}")})
    elif "completion_message" in data:
        msg = data["completion_message"]
        content = msg.get("content")
        text = content.get("text", "") if isinstance(content, dict) else (content or "")
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function", tc)
            calls.append({"id": tc.get("id"), "name": fn["name"], "arguments": fn.get("arguments", "{}")})

    usage = Usage()
    u = data.get("usage") or {}
    usage.input_tokens = int(u.get("prompt_tokens", u.get("input_tokens", 0)) or 0)
    usage.output_tokens = int(u.get("completion_tokens", u.get("output_tokens", 0)) or 0)
    for metric in data.get("metrics") or []:
        if metric.get("metric") == "num_prompt_tokens":
            usage.input_tokens = int(metric["value"])
        elif metric.get("metric") == "num_completion_tokens":
            usage.output_tokens = int(metric["value"])
    return text, calls, usage


Transport = Callable[[dict], dict]   # request body → response JSON (raises ModelError on failure)


class ModelClient:
    _lock = threading.Lock()   # guards the spend total + reservations across threads (parallel compile)

    def __init__(self, mode: Optional[str] = None, budget_usd: Optional[float] = None,
                 cassette_dir: Optional[Path] = None, cost_log: Optional[Path] = None,
                 transport: Optional[Transport] = None):
        self.mode = mode or config.model_mode()
        if self.mode not in config.MODEL_MODES:
            raise ValueError(f"mode must be one of {config.MODEL_MODES}")
        self.budget_usd = config.budget_usd() if budget_usd is None else budget_usd
        self.cassettes = Cassettes(cassette_dir)
        self.cost_log = Path(cost_log or config.COST_LOG)
        self._transport = transport
        self._reserved = 0.0

    # ---- spend -------------------------------------------------------------------------------
    def spent_usd(self) -> float:
        if not self.cost_log.exists():
            return 0.0
        total = 0.0
        for line in self.cost_log.read_text(encoding="utf-8").splitlines():
            if line.strip():
                total += float(json.loads(line).get("cost_usd", 0.0))
        return total

    def _log(self, entry: dict) -> None:
        self.cost_log.parent.mkdir(parents=True, exist_ok=True)
        with self.cost_log.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def _reserve(self, estimate: float) -> None:
        with self._lock:
            spent = self.spent_usd()
            if spent + self._reserved + estimate > self.budget_usd:
                raise BudgetExceeded(
                    f"call refused: worst case ${estimate:.4f} + spent ${spent:.4f}"
                    f"{f' + in flight ${self._reserved:.4f}' if self._reserved else ''}"
                    f" would pass the ${self.budget_usd:.2f} budget (BUDGET_USD). "
                    "Use MODEL_MODE=replay, lower max_tokens, or raise the cap on purpose.")
            self._reserved += estimate

    def _release(self, estimate: float) -> None:
        with self._lock:
            self._reserved = max(0.0, self._reserved - estimate)

    # ---- calls -------------------------------------------------------------------------------
    def chat(self, model: str, messages: list[dict], *, max_tokens: int, tools: Optional[list[dict]] = None,
             tool_choice: Optional[Any] = None, temperature: Optional[float] = 0.0,
             response_format: Optional[dict] = None, reasoning_effort: Optional[str] = None,
             tag: str = "") -> Reply:
        if not 1 <= max_tokens <= MAX_TOKENS_CEILING:
            raise ValueError(f"max_tokens must be 1..{MAX_TOKENS_CEILING} (it bounds the budget estimate)")
        if _count_images(messages) > config.MAX_IMAGES:
            raise ValueError(f"more than {config.MAX_IMAGES} images in one request (Meta's limit)")

        request: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens}
        if tools:
            request["tools"] = tools
        if tool_choice is not None:
            request["tool_choice"] = tool_choice
        if temperature is not None:
            request["temperature"] = temperature
        if response_format is not None:
            request["response_format"] = response_format
        if reasoning_effort is not None:
            request["reasoning_effort"] = reasoning_effort
        key = request_key(request)

        if self.mode == "replay" or (self.mode == "record" and self.cassettes.has(key)):
            return self._reply(self.cassettes.load(key, request), model, key, from_cassette=True)

        estimate = estimate_cost(request)
        self._reserve(estimate)
        started = time.monotonic()
        try:
            data = self._send(request)
        finally:
            self._release(estimate)

        reply = self._reply(data, model, key, from_cassette=False)
        if reply.usage.input_tokens == 0 and reply.usage.output_tokens == 0:
            reply.cost_usd = estimate   # no usage reported: log the worst case so the total never undercounts
        self._log({
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "mode": self.mode,
            "model": model, "tag": tag, "key": key,
            "input_tokens": reply.usage.input_tokens, "output_tokens": reply.usage.output_tokens,
            "estimate_usd": round(estimate, 6), "cost_usd": round(reply.cost_usd, 6),
            "seconds": round(time.monotonic() - started, 2),
        })
        if self.mode == "record":
            self.cassettes.save(key, request, data)
        return reply

    def _reply(self, data: dict, model: str, key: str, from_cassette: bool) -> Reply:
        text, calls, usage = parse_response(data)
        parsed = []
        for c in calls:
            try:
                parsed.append(parse_tool_call(c["name"], c["arguments"]))
            except (ValueError, TypeError, json.JSONDecodeError):
                pass   # not one of our tools (e.g. web_search); still in raw_tool_calls
        return Reply(text=text, tool_calls=parsed, raw_tool_calls=calls, usage=usage,
                     cost_usd=0.0 if from_cassette else cost_of(model, usage),
                     from_cassette=from_cassette, cassette_key=key, raw=data)

    def _send(self, request: dict) -> dict:
        if self._transport:
            return self._transport(request)
        return _http_send(request)


def _http_send(request: dict, retries: int = 2) -> dict:
    import httpx

    key = config.env("META_API_KEY")
    if not key:
        raise ModelError("META_API_KEY is not set (needed for MODEL_MODE=live/record)")
    url = config.env("META_BASE_URL", "https://api.meta.ai/v1").rstrip("/") + config.env("META_CHAT_PATH", "/chat/completions")
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    for attempt in range(retries + 1):
        try:
            r = httpx.post(url, json=request, headers=headers, timeout=120)
        except httpx.HTTPError as e:
            if attempt == retries:
                raise ModelError(f"network error calling {url}: {e}") from e
        else:
            if r.status_code == 200:
                return r.json()
            if r.status_code not in (429, 500, 502, 503, 504) or attempt == retries:
                raise ModelError(f"{r.status_code} from {url}: {r.text[:500]}")
        time.sleep(2 ** (attempt + 1))
    raise ModelError("unreachable")
