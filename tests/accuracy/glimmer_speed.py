"""Glimmer speed test (phase 1, free, runs on the author's GPU): is local Muse Glimmer fast and right enough for step checks?

For each case (screenshot + `check` sentence + expected answer) it asks Glimmer "done / not_yet / wrong?"
and measures cold start, warm latency and accuracy, at full size and downscaled.

Pass: warm median <= --target-s (default 3 s) at 1280 px, and every case answered as expected.
Slow or wrong → plan B from 02 Meta models: Modal (free tier) → Spark Contributor.

Setup on Windows (see 00 Context, "Run locally"):
  1. Install Ollama, pull Glimmer (4-bit, ~20 GB), and note its name in `ollama list`.
  2. Take the screenshots listed in tests/fixtures/screens/glimmer_cases.yaml (Win+Shift+S, save as PNG there).
  3. py -m tests.accuracy.glimmer_speed --model <name from ollama list>

Results: cache/logs/glimmer_speed.json. The prompt and answer parser are shared with live/verify.py later.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import re
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from engine import config

CASES = config.ROOT / "tests/fixtures/screens/glimmer_cases.yaml"
VERDICTS = ("done", "not_yet", "wrong")

PROMPT = """You check one step of a software tutorial against a screenshot of the user's screen.
Step goal: {title}
Success looks like: {check}
Answer with JSON only: {{"state": "done" | "not_yet" | "wrong", "why": "<one short sentence>"}}
- done: the screenshot clearly shows the success state.
- not_yet: the success state is not visible and nothing contradicts it.
- wrong: the screen shows a different result than the step asks for."""


def build_prompt(title: str, check: str) -> str:
    return PROMPT.format(title=title, check=check)


def parse_verdict(text: str) -> str:
    """done / not_yet / wrong from Glimmer's reply; `unsure` if it can't be read."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if m:
        try:
            state = str(json.loads(m.group(0)).get("state", "")).strip().lower().replace(" ", "_").replace("-", "_")
            if state in VERDICTS:
                return state
        except (json.JSONDecodeError, AttributeError):
            pass
    low = (text or "").lower()
    for v in ("not_yet", "not yet", "wrong", "done"):
        if re.search(rf"\b{v}\b", low):
            return v.replace(" ", "_")
    return "unsure"


def downscale(png: bytes, max_side: Optional[int]) -> bytes:
    if not max_side:
        return png
    from PIL import Image

    im = Image.open(io.BytesIO(png))
    if max(im.size) <= max_side:
        return png
    im.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def ask_ollama(host: str, model: str, prompt: str, png: bytes, timeout: float, think: Optional[str] = "low") -> dict:
    """think: Glimmer always reasons first (it can't be switched off); "low" keeps the trace short. None = omit."""
    import httpx

    body = {"model": model, "stream": False, "format": "json", "options": {"temperature": 0},
            "messages": [{"role": "user", "content": prompt, "images": [base64.b64encode(png).decode()]}]}
    if think:
        body["think"] = think
    t0 = time.perf_counter()
    r = httpx.post(f"{host.rstrip('/')}/api/chat", timeout=timeout, json=body)
    r.raise_for_status()
    data = r.json()
    secs = time.perf_counter() - t0
    tok_s = None
    if data.get("eval_count") and data.get("eval_duration"):
        tok_s = data["eval_count"] / (data["eval_duration"] / 1e9)
    msg = data.get("message", {})
    return {"text": msg.get("content", ""), "thinking_chars": len(msg.get("thinking") or ""), "seconds": secs,
            "load_seconds": (data.get("load_duration") or 0) / 1e9, "tokens_per_s": tok_s}


def load_cases(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    cases = []
    for c in data["cases"]:
        img = path.parent / c["image"]
        cases.append({**c, "path": img, "present": img.exists()})
    return cases


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=config.env("GLIMMER_OLLAMA_MODEL", "muse-glimmer"))
    ap.add_argument("--host", default=config.env("OLLAMA_HOST", "http://127.0.0.1:11434"))
    ap.add_argument("--cases", default=str(CASES))
    ap.add_argument("--sizes", default="1280,0", help="max image side per pass; 0 = full size")
    ap.add_argument("--repeats", type=int, default=3, help="warm runs per case and size")
    ap.add_argument("--target-s", type=float, default=3.0)
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--think", default="low", help='Ollama "think" level (low/medium/high); "" to omit')
    args = ap.parse_args(argv)

    cases = load_cases(Path(args.cases))
    missing = [str(c["path"]) for c in cases if not c["present"]]
    cases = [c for c in cases if c["present"]]
    if missing:
        print("missing screenshots (skipped):\n  " + "\n  ".join(missing))
    if not cases:
        print("no screenshots yet; see the header of glimmer_cases.yaml")
        return 2

    sizes = [int(s) for s in args.sizes.split(",")]
    print(f"model {args.model} at {args.host}; {len(cases)} cases; sizes {sizes}")

    # Cold start: first call loads the weights.
    first = cases[0]
    cold = ask_ollama(args.host, args.model, build_prompt(first["title"], first["check"]),
                      downscale(first["path"].read_bytes(), sizes[0]), args.timeout, args.think or None)
    print(f"cold call {cold['seconds']:.1f}s (load {cold['load_seconds']:.1f}s)")

    results, by_size = [], {}
    for size in sizes:
        lat = []
        for c in cases:
            png = downscale(c["path"].read_bytes(), size)
            prompt = build_prompt(c["title"], c["check"])
            for i in range(args.repeats):
                a = ask_ollama(args.host, args.model, prompt, png, args.timeout, args.think or None)
                verdict = parse_verdict(a["text"])
                ok = verdict == c["expect"]
                lat.append(a["seconds"])
                results.append({"case": c["id"], "size": size or "full", "run": i + 1, "seconds": round(a["seconds"], 2),
                                "tokens_per_s": a["tokens_per_s"] and round(a["tokens_per_s"], 1),
                                "thinking_chars": a["thinking_chars"],
                                "verdict": verdict, "expect": c["expect"], "ok": ok, "reply": a["text"][:300]})
                print(f"  [{size or 'full'}] {c['id']:<28} {a['seconds']:5.1f}s  {verdict:<8} {'ok' if ok else 'MISS (want ' + c['expect'] + ')'}")
        by_size[str(size or "full")] = {
            "median_s": round(statistics.median(lat), 2),
            "p90_s": round(sorted(lat)[max(0, int(len(lat) * 0.9) - 1)], 2),
            "accuracy": round(sum(r["ok"] for r in results if r["size"] == (size or "full")) /
                              sum(1 for r in results if r["size"] == (size or "full")), 3),
        }

    main_size = str(sizes[0] or "full")
    verdict = ("PASS" if by_size[main_size]["median_s"] <= args.target_s and by_size[main_size]["accuracy"] == 1.0
               else "SLOW" if by_size[main_size]["median_s"] > args.target_s else "INACCURATE")
    summary = {"model": args.model, "think": args.think or None, "cold_seconds": round(cold["seconds"], 1), "by_size": by_size,
               "target_s": args.target_s, "verdict": verdict, "missing_screenshots": missing}
    out = config.LOGS / "glimmer_speed.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"run_at": datetime.now().isoformat(timespec="seconds"), "summary": summary,
                               "results": results}, indent=2), encoding="utf-8")
    print("\n" + json.dumps(summary, indent=2))
    print(f"saved {out}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
