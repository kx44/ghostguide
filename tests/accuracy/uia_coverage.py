"""UIA coverage test (phase 1, Windows only): how much of each gold tutorial can Windows UI Automation see?

Two questions per step:
  1. Target: can UIA find the step's control (label or alias, matching type) with an on-screen box?  → live step 4b
  2. Verify: once the step is done, does its `verify.uia` hint come out true?                        → live step 9a

Modes
  --snapshot  One pass, no interaction. Dumps every UIA element of the app window and reports which
              step targets are visible right now. Quick first look; most targets only appear mid-tutorial.
  --walk      Step by step. Before each step it probes the target; you do the step (yourself), press
              Enter, and it probes the `verify` hint. Enter = done, s = skip step, q = stop and report.
              Use --from N / --to M to walk part of a tutorial.

Run from the repo root on Windows (see 00 Context, "Run locally"):
  py -m tests.accuracy.uia_coverage --app vscode --walk
  py -m tests.accuracy.uia_coverage --app solidworks --walk

Results: cache/logs/uia_coverage-<app>.json (+ the element dump for --snapshot).
The matching functions below are pure (they work on dumped element dicts), so they are unit-tested on Linux.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from engine import config
from engine.basefile.parse import parse_file
from engine.schema.tutorial import Step, UiaCheck

APPS = {
    "vscode": {"window": "Visual Studio Code", "also": ["Google Chrome"], "tutorial": "tutorials/youtube-clone-vscode.md"},
    "solidworks": {"window": "SOLIDWORKS", "also": [], "tutorial": "tutorials/mug-solidworks.md"},
}
# Target kind → UIA control types that count as a match. Canvas-like kinds are drawn, not exposed.
KIND_TYPES = {
    "button": {"Button", "SplitButton", "MenuItem", "ListItem", "CheckBox", "RadioButton", "TabItem", "Hyperlink"},
    "tab": {"TabItem"},
    "menu_item": {"MenuItem", "Button", "ListItem"},
    "field": {"Edit", "ComboBox", "Document", "Spinner"},
    "tree_item": {"TreeItem", "ListItem", "DataItem"},
    "window": {"Window", "Pane"},
}
NOT_UIA = {"canvas", "face", "edge"}


# ---------- pure matching (unit-tested) ----------------------------------------------------------
def _norm(s: Optional[str]) -> str:
    return " ".join((s or "").replace("…", "...").split()).casefold()


# VS Code appends key hints to UIA names: "Toggle Panel (Ctrl+J)", "Split Editor Right (Ctrl+\) [Alt] Split Editor Down".
_HINTS = re.compile(r"\s*(\[alt\].*|\((ctrl|alt|shift|win|f\d+)[^)]*\))\s*$")


def _base_name(name: str) -> str:
    prev = None
    while prev != name:
        prev, name = name, _HINTS.sub("", name)
    return name


def _on_screen(el: dict) -> bool:
    r = el.get("rect")
    return bool(r) and r[2] > 0 and r[3] > 0 and not el.get("offscreen", False)


def match_target(step: Step, elements: Iterable[dict], window: Optional[str] = None) -> dict:
    """Best UIA element for the step's target. quality: exact > alias > contains > none, or n/a for canvas.
    window: only elements whose top-level title contains it (window-kind targets look everywhere).
    "contains" needs whole words and a matching control type, so "Editor" ≠ "Open Editors Section"."""
    kind = step.target.kind
    if kind in NOT_UIA:
        return {"quality": "n/a", "reason": f"{kind} targets are drawn, not UIA controls"}
    names = [_norm(step.target.label)] + [_norm(a) for a in step.target.aliases or []]
    types = KIND_TYPES.get(kind, set())
    best = None
    for el in elements:
        if not _on_screen(el):
            continue
        if window and kind != "window" and window.casefold() not in (el.get("window") or "").casefold():
            continue
        name = _base_name(_norm(el.get("name")))
        if not name:
            continue
        type_ok = el.get("type") in types
        if name == names[0]:
            q = "exact"
        elif name in names[1:]:
            q = "alias"
        elif type_ok and len(name) <= 4 * max(len(n) for n in names) and any(
                n and re.search(rf"(?<!\w){re.escape(n)}(?!\w)", name) for n in names):
            q = "contains"
        else:
            continue
        score = {"exact": 3, "alias": 2, "contains": 1}[q] + (0.5 if type_ok else 0)
        if not best or score > best[0]:
            best = (score, q, type_ok, el)
    if not best:
        return {"quality": "none"}
    _, q, type_ok, el = best
    return {"quality": q, "type_ok": type_ok, "name": el.get("name"), "type": el.get("type"), "rect": el.get("rect")}


def eval_uia_check(check: UiaCheck, elements: Iterable[dict]) -> bool:
    """True when the check holds over the dumped elements (all given fields must match one element)."""
    def hit(el: dict) -> bool:
        if check.window and check.window.casefold() not in (el.get("window") or "").casefold():
            return False
        if check.type and el.get("type") != check.type:
            return False
        if check.name is not None and _norm(el.get("name")) != _norm(check.name):
            return False
        if check.name_contains and _norm(check.name_contains) not in _norm(el.get("name")):
            return False
        if check.value is not None and el.get("value") != check.value:
            return False
        if check.value_contains and check.value_contains not in (el.get("value") or ""):
            return False
        if check.selected is not None and el.get("selected") is not check.selected:
            return False
        return True

    found = any(hit(el) for el in elements)
    return found if check.exists else not found


def summarise(rows: list[dict]) -> dict:
    uia_targets = [r for r in rows if r.get("target", {}).get("quality") not in (None, "n/a")]
    found = [r for r in uia_targets if r["target"]["quality"] != "none"]
    verified = [r for r in rows if r.get("verify") is not None]
    true = [r for r in verified if r["verify"]]
    return {
        "steps_probed": len(rows),
        "targets_uia_kind": len(uia_targets),
        "targets_found": len(found),
        "target_coverage": round(len(found) / len(uia_targets), 3) if uia_targets else None,
        "canvas_targets": sum(1 for r in rows if r.get("target", {}).get("quality") == "n/a"),
        "verify_hints_probed": len(verified),
        "verify_hints_true": len(true),
        "verify_coverage": round(len(true) / len(verified), 3) if verified else None,
        "missed_targets": [f"{r['n']}: {r['label']}" for r in uia_targets if r["target"]["quality"] == "none"],
        "failed_verify": [f"{r['n']}: {r['title']}" for r in verified if not r["verify"]],
    }


# ---------- Windows UIA layer --------------------------------------------------------------------
def dump_elements(window_title: str, also: Iterable[str] = (), max_depth: int = 60,
                  max_elements: int = 30000) -> list[dict]:
    """Every UIA element under top-level windows whose title contains window_title or one of `also`
    (Chrome for the VS Code tutorial's browser steps)."""
    import uiautomation as auto

    wanted = [window_title.casefold()] + [a.casefold() for a in also]
    out: list[dict] = []
    for top in auto.GetRootControl().GetChildren():
        title = top.Name or ""
        if not any(w in title.casefold() for w in wanted):
            continue
        for ctrl, _depth in auto.WalkControl(top, includeTop=True, maxDepth=max_depth):
            if len(out) >= max_elements:
                break
            try:
                r = ctrl.BoundingRectangle
                el = {"window": title, "name": ctrl.Name, "type": ctrl.ControlTypeName.removesuffix("Control"),
                      "rect": [r.left, r.top, r.width(), r.height()], "offscreen": bool(ctrl.IsOffscreen)}
                vp = ctrl.GetPattern(auto.PatternId.ValuePattern)
                if vp:
                    el["value"] = vp.Value
                sp = ctrl.GetPattern(auto.PatternId.SelectionItemPattern)
                if sp:
                    el["selected"] = bool(sp.IsSelected)
            except Exception as e:   # elements vanish mid-walk; keep going
                el = {"window": title, "error": str(e)}
            out.append(el)
    return out


def probe_step(step: Step, app: dict, phase: str) -> tuple[dict, float]:
    t0 = time.perf_counter()
    els = dump_elements(app["window"], app["also"])
    secs = time.perf_counter() - t0
    if phase == "target":
        return match_target(step, els, app["window"]), secs
    checks = step.verify.uia_checks() if step.verify else []
    return {"checks": [eval_uia_check(c, els) for c in checks]}, secs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--app", choices=APPS, required=True)
    ap.add_argument("--tutorial", help="base .md (default: the app's gold file)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--snapshot", action="store_true")
    mode.add_argument("--walk", action="store_true")
    ap.add_argument("--from", dest="start", type=int, default=1)
    ap.add_argument("--to", dest="end", type=int, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--window", help='window title part, e.g. "youtube-clone - Visual Studio Code" when several are open')
    args = ap.parse_args(argv)

    if sys.platform != "win32":
        print("UIA coverage needs Windows (UI Automation). Listed under 'Run locally' in 00 Context.")
        return 2
    from engine.dpi import make_dpi_aware
    print(f"DPI awareness: {make_dpi_aware()}")

    app = dict(APPS[args.app])
    if args.window:
        app["window"] = args.window
    tut = parse_file(config.ROOT / (args.tutorial or app["tutorial"]))
    steps = [s for s in tut.steps if args.start <= s.n <= (args.end or len(tut.steps))]
    out = Path(args.out or config.LOGS / f"uia_coverage-{args.app}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    if args.snapshot:
        t0 = time.perf_counter()
        els = dump_elements(app["window"], app["also"])
        print(f"{len(els)} elements in {time.perf_counter() - t0:.1f}s")
        (out.with_suffix(".elements.json")).write_text(json.dumps(els, indent=1, ensure_ascii=False), encoding="utf-8")
        for s in steps:
            rows.append({"n": s.n, "title": s.title, "label": s.target.label, "kind": s.target.kind,
                         "target": match_target(s, els, app["window"])})
    else:
        print(f"Walking {tut.meta.title}: steps {steps[0].n}-{steps[-1].n}. Start state:\n  {tut.meta.start_state}\n")
        for s in steps:
            print(f"--- Step {s.n} — {s.title}  [{s.action} → {s.target.label} ({s.target.kind})]")
            if s.target.where:
                print(f"    where: {s.target.where}")
            for k, v in s.params.items():
                v = str(v).rstrip("\n")
                print(f"    {k}:" + ("\n" + "\n".join("      " + line for line in v.splitlines()) if "\n" in v else f" {v}"))
            print(f"    done when: {s.check}")
            target, t_secs = probe_step(s, app, "target")
            print(f"    target: {target.get('quality')} {target.get('name') or ''} {target.get('type') or ''} {target.get('rect') or ''} ({t_secs:.1f}s)")
            row = {"n": s.n, "title": s.title, "label": s.target.label, "kind": s.target.kind,
                   "target": target, "target_seconds": round(t_secs, 2)}
            ans = input("    do the step, then Enter (s = skip, q = quit): ").strip().lower()
            if ans == "q":
                rows.append(row)
                break
            if ans == "s":
                row["skipped"] = True
            elif s.verify and s.verify.uia_checks():
                res, v_secs = probe_step(s, app, "verify")
                row["verify"] = all(res["checks"])
                row["verify_detail"] = res["checks"]
                print(f"    verify: {'TRUE' if row['verify'] else 'false'} {res['checks']} ({v_secs:.1f}s)")
            rows.append(row)

    summary = summarise(rows)
    out.write_text(json.dumps({"app": args.app, "tutorial": tut.meta.title,
                               "run_at": datetime.now().isoformat(timespec="seconds"),
                               "mode": "snapshot" if args.snapshot else "walk",
                               "summary": summary, "steps": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n" + json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"\nsaved {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
