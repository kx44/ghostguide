"""The two model rungs of the check ladder (live steps 9c and 9d): "here is a screenshot and what should be
true now; done, not yet, or wrong?"

  9c Muse Glimmer on Modal    GLIMMER_BACKEND=modal, GLIMMER_MODAL_URL = the deployed endpoint
  9d Spark Contributor        through models/client.py (record/replay, cost log, the $4 cap)

Both are **off** unless CHECK_MODELS=on: they only run after the free checks (rule, pixel diff) couldn't tell,
and they cost money (Spark) or need a Modal deployment (Glimmer). With CHECK_MODELS=on and no META_API_KEY,
Spark answers from recordings only (MODEL_MODE=replay) and anything unrecorded is "unknown".

Modal endpoint contract (deploy/modal_glimmer.py; header `Authorization: Bearer <GLIMMER_MODAL_TOKEN>`): POST JSON
{"image_b64": "...", "image_mime": "image/jpeg", "question": "...", "check": "..."}
→ {"result": "done|not_yet|wrong", "why": "..."}.
"""
from __future__ import annotations

import base64
import json
import re
from typing import Callable, Optional

from engine import config
from engine.schema.tutorial import Step

# Spark's reasoning counts toward max_tokens, so leave room beyond the short JSON answer.
MAX_TOKENS = 600
EFFORT = "low"
# A cold Modal container loads the weights first (about a minute); past this the ladder falls through to Spark.
MODAL_TIMEOUT_S = 90
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
        reply = c.chat(model=config.SPARK_CONTRIBUTOR, max_tokens=MAX_TOKENS, reasoning_effort=EFFORT,
                       tag=f"check-step-{step.n}",
                       messages=[{"role": "user", "content": [text_part(question(step)), image_part(png)]}])
        v = parse_answer(reply.text)
        v.stage = "spark"
        return v
    return check


def as_jpeg(png: bytes, quality: int = 85) -> bytes:
    """Less than half the bytes of the PNG; the upload to Modal (us-east) is part of every check's time."""
    import io
    from PIL import Image

    buf = io.BytesIO()
    Image.open(io.BytesIO(png)).convert("RGB").save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def glimmer_modal(url: str, post=None) -> Callable[[Step, bytes], object]:
    def check(step: Step, png: bytes):
        body = {"image_b64": base64.b64encode(as_jpeg(png)).decode(), "image_mime": "image/jpeg",
                "question": question(step), "check": step.check}
        if post is None:
            import httpx
            headers = {"Authorization": f"Bearer {config.env('GLIMMER_MODAL_TOKEN')}"}
            r = httpx.post(url, json=body, headers=headers, timeout=MODAL_TIMEOUT_S)
            r.raise_for_status()
            data = r.json()
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
