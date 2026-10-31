"""Model rungs of the check ladder: do Spark Contributor and Glimmer on Modal answer the step checks right?

Same cases as glimmer_speed.py (tests/fixtures/screens/glimmer_cases.yaml: screenshot + check + expected answer),
asked through the real ladder code in engine/models/glimmer.py, so the prompt and parser are the live ones.

  py -m tests.accuracy.check_models                 # both rungs (Glimmer only if GLIMMER_MODAL_URL is set)
  py -m tests.accuracy.check_models --only spark

Spark goes through models/client.py: MODEL_MODE decides (record = pay once, then replay for free), and the
$4 cap applies. Results: cache/logs/check_models.json.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from engine import config
from engine.models import glimmer
from tests.accuracy.glimmer_speed import CASES, downscale, load_cases


def as_step(i: int, case: dict):
    """Just the fields glimmer.question() reads; the cases have no action/target, so a neutral one."""
    return SimpleNamespace(n=100 + i, title=case["title"], action="do", check=case["check"],
                           target=SimpleNamespace(label="the step", where=None))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", default=str(CASES))
    ap.add_argument("--only", choices=("spark", "glimmer"))
    ap.add_argument("--max-side", type=int, default=1280, help="downscale screenshots to this; 0 = full size")
    args = ap.parse_args(argv)

    cases = [c for c in load_cases(Path(args.cases)) if c["present"]]
    rungs = {}
    if args.only in (None, "spark"):
        rungs["spark"] = glimmer.spark_contributor()
    url = config.env("GLIMMER_MODAL_URL")
    if args.only in (None, "glimmer"):
        if url:
            rungs["glimmer"] = glimmer.glimmer_modal(url)
        else:
            print("glimmer: GLIMMER_MODAL_URL not set, skipped")

    results, summary = [], {}
    for name, check in rungs.items():
        ok_count, secs = 0, []
        for i, c in enumerate(cases):
            png = downscale(c["path"].read_bytes(), args.max_side or None)
            t0 = time.perf_counter()
            try:
                v = check(as_step(i, c), png)
                result, why = v.result, v.why
            except Exception as e:
                result, why = "error", str(e)[:200]
            s = time.perf_counter() - t0
            ok = result == c["expect"]
            ok_count += ok
            secs.append(s)
            results.append({"rung": name, "case": c["id"], "result": result, "expect": c["expect"], "ok": ok,
                            "seconds": round(s, 2), "why": why})
            print(f"  [{name}] {c['id']:<28} {s:5.1f}s  {result:<8} {'ok' if ok else 'MISS (want ' + c['expect'] + ')'}  {why}")
        summary[name] = {"right": ok_count, "of": len(cases), "max_s": round(max(secs), 1) if secs else None}

    out = config.LOGS / "check_models.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"run_at": datetime.now().isoformat(timespec="seconds"), "summary": summary,
                               "results": results}, indent=2), encoding="utf-8")
    print("\n" + json.dumps(summary, indent=2))
    return 0 if all(s["right"] == s["of"] for s in summary.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
