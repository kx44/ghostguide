"""The two model rungs of the check ladder (live steps 9c and 9d): "here is a screenshot and what should be
true now; done, not yet, or wrong?"

  9c Muse Glimmer on Modal    GLIMMER_BACKEND=modal, GLIMMER_MODAL_URL = the deployed endpoint
  9d Spark Contributor        through models/client.py (record/replay, cost log, the $4 cap)

Both are **off** unless CHECK_MODELS=on: they only run after the free checks (rule, pixel diff) couldn't tell,
and they cost money (Spark) or need a Modal deployment (Glimmer). With CHECK_MODELS=on and no META_API_KEY,
Spark answers from recordings only (MODEL_MODE=replay) and anything unrecorded is "unknown".

Modal endpoint contract (what the deployment must accept): POST JSON
{"image_png_b64": "...", "question": "...", "check": "..."} → {"result": "done|not_yet|wrong", "why": "..."}.
"""
from __future__ import annotations

import base64
import json
import re
from typing import Callable, Optional

from engine import config
from engine.schema.tutorial import Step

MAX_TOKENS = 120
PROMPT = (
    "You check one step of a software tutorial from a screenshot of the user's screen.\n"
    "Step: {title}\nWhat the user was asked to do: {what}\nWhen it's done: {check}\n"
    "Answer with JSON only: {{\"result\": \"done\" | \"not_yet\" | \"wrong\", \"why\": \"<one short sentence>\"}}. "
    "Say done only if the screenshot clearly shows it; not_yet if it simply hasn't happened; wrong if something "
    "else happened instead (a wrong value, the wrong file)."
)


def enabled() -> bool:
    return config.env("CHECK_MODELS", "off").lower() in ("on", "1", "true", "yes")


def question(step: Step) -> str:
    what = f"{step.action} {step.target.label}" + (f" ({step.target.where})" if step.target.where else "")
    return PROMPT.format(title=step.title, what=what, check=step.check)


def parse_answer(text: str):
    """The model's JSON (possibly wrapped in prose or a code fence) → Verdict; anything else = unknown."""
    from engine.live.verify import Verdict

    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return Verdict("unknown", why="no JSON in the answer")
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return Verdict("unknown", why="unreadable answer")
    result = str(data.get("result", "")).strip().lower().replace(" ", "_")
    if result not in ("done", "not_yet", "wrong"):
        return Verdict("unknown", why=f"unexpected result {result!r}")
    return Verdict(result, why=str(data.get("why", ""))[:160])


def spark_contributor(client=None) -> Callable[[Step, bytes], object]:
    from engine.models.client import ModelClient, image_part, text_part

    c = client or ModelClient()

    def check(step: Step, png: bytes):
        reply = c.chat(model=config.SPARK_CONTRIBUTOR, max_tokens=MAX_TOKENS, tag=f"check-step-{step.n}",
                       messages=[{"role": "user", "content": [text_part(question(step)), image_part(png)]}])
        v = parse_answer(reply.text)
        v.stage = "spark"
        return v
    return check


def glimmer_modal(url: str, post=None) -> Callable[[Step, bytes], object]:
    def check(step: Step, png: bytes):
        body = {"image_png_b64": base64.b64encode(png).decode(), "question": question(step), "check": step.check}
        if post is None:
            import httpx
            data = httpx.post(url, json=body, timeout=30).json()
        else:
            data = post(url, body)
        v = parse_answer(json.dumps(data))
        v.stage = "glimmer"
        return v
    return check


def check_stages() -> tuple[Optional[Callable], Optional[Callable]]:
    """(glimmer, spark) for the ladder; (None, None) while CHECK_MODELS is off."""
    if not enabled():
        return None, None
    glimmer = None
    url = config.env("GLIMMER_MODAL_URL")
    if config.env("GLIMMER_BACKEND", "modal") == "modal" and url:
        glimmer = glimmer_modal(url)
    return glimmer, spark_contributor()
