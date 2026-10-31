"""Spark ribbon accuracy (phase 1's leftover, tuned in phase 4): does Spark find controls on the SOLIDWORKS ribbon?

Cases: tests/fixtures/screens/spark_ribbon_cases.yaml (screenshot + hand-labelled box per control). A control hits
when the center of Spark's box is inside the true box; a control that isn't on the tab must not be pointed at.
Goes through the live finder code (locate/vision.py), once with the whole window scaled down and once with just
the ribbon strip, so the two can be compared.

    py -m tests.accuracy.spark_ribbon                       # both pictures
    py -m tests.accuracy.spark_ribbon --mode ribbon

MODEL_MODE decides (record = pay once, then replay for free), the $4 cap applies. ~$0.02 per call.
Results: cache/logs/spark_ribbon.json.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from types import SimpleNamespace

import yaml

from engine import config
from engine.live.locate.vision import SparkVision

CASES = config.ROOT / "tests" / "fixtures" / "screens" / "spark_ribbon_cases.yaml"
DISPLAY_SCALE = 1.5     # of the labelled screenshots


def hit(box, truth) -> bool:
    """Center of the found box inside the true one."""
    cx, cy = box.x + box.w / 2, box.y + box.h / 2
    x, y, w, h = truth
    return x <= cx <= x + w and y <= cy <= y + h


def score(found, truth) -> bool:
    return (found is None) if truth is None else (found is not None and hit(found, truth))


def as_step(i: int, case: dict):
    return SimpleNamespace(n=200 + i, title=f"Click {case['label']}", action="click", params={},
                           target=SimpleNamespace(label=case["label"], kind=case["kind"], where=case["where"]))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=("window", "ribbon", "both"), default="both")
    args = ap.parse_args(argv)

    from PIL import Image

    data = yaml.safe_load(CASES.read_text(encoding="utf-8"))
    modes = ("window", "ribbon") if args.mode == "both" else (args.mode,)
    results, summary = [], {}
    for mode in modes:
        right = total = 0
        for image, cases in data["images"].items():
            path = CASES.parent / image
            if not path.exists():
                print(f"  {image}: missing, skipped")
                continue
            img = Image.open(path).convert("RGB")
            for i, c in enumerate(cases):
                v = SparkVision("SOLIDWORKS", grab=lambda: (img, (0, 0), DISPLAY_SCALE), regions=mode == "ribbon")
                box = v.find(as_step(i, c))
                ok = score(box, c["box"])
                right += ok
                total += 1
                got = [box.x, box.y, box.w, box.h] if box else (v.last_route or v.last_how)
                results.append({"mode": mode, "image": image, "label": c["label"], "truth": c["box"], "got": got,
                                "ok": ok, "how": v.last_how})
                print(f"  [{mode:6}] {c['label']:<22} {'ok  ' if ok else 'MISS'} got {got}  want {c['box']}")
        summary[mode] = {"right": right, "of": total}
    out = config.LOGS / "spark_ribbon.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"run_at": datetime.now().isoformat(timespec="seconds"), "summary": summary,
                               "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n" + json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
