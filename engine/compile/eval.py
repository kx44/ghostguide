"""Score a compiled tutorial against its gold file (compile step 9). Plain code, no model, same answer every run.

Steps are lined up in order (best total similarity), then counted. Two numbers for a source whose gold file has a
`<gold>.differences.yaml`: `raw` against every gold step, and `fair`, which applies only what that file lists.
Raw stays the headline. The files' hashes go in the score, so a score can't quietly move to an edited gold file.
"""
from __future__ import annotations

import difflib
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from engine import config
from engine.basefile.parse import parse_file
from engine.schema.tutorial import Step, Tutorial

MATCH_AT = 0.45        # a pair below this isn't the same step
SOURCE_SLACK_S = 5     # a video step's time counts as right this close to gold's
# Set before the first compile. The mug's are in its differences file.
TARGETS = {"youtube-clone-vscode.md": {"steps_f1_raw": 0.85, "typed_exact": 0.90}}


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", (text or "").casefold()))


def _overlap(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def _value(step: Step) -> str:
    p = step.params
    v = p.get("value")
    if v is None and isinstance(p.get("suggested"), dict):
        v = p["suggested"].get("value")
    return "" if v is None else str(v)


def _squeeze(text: str) -> str:
    return re.sub(r"\s+", "", text)


def label_score(c: Step, g: Step, extra: Optional[list[str]] = None) -> float:
    names = [g.target.label, *(g.target.aliases or []), *(extra or [])]
    cl = c.target.label
    if any(cl.casefold().strip() == n.casefold().strip() for n in names):
        return 1.0
    return max(_overlap(cl, n) for n in names)


def similarity(c: Step, g: Step, diff: Optional[dict] = None) -> float:
    """0..1: the same action on the same control with the same value. Typed text decides type steps."""
    diff = diff or {}
    if c.action == "type" and g.action == "type" and (_value(c) or _value(g)):
        text = difflib.SequenceMatcher(None, _squeeze(_value(c)), _squeeze(_value(g)), autojunk=False).ratio()
        return 0.15 + 0.15 * label_score(c, g) + 0.7 * text
    same = c.action == g.action or c.action in diff.get("actions", [])
    title = _overlap(c.title, g.title)
    label = label_score(c, g, diff.get("labels"))
    return 0.3 * same + 0.5 * label + 0.2 * title


def align(compiled: list[Step], gold: list[Step], diffs: Optional[dict[int, dict]] = None) -> list[tuple[int, int, float]]:
    """Order-keeping alignment: (compiled index, gold index, similarity) for the pairs at or above MATCH_AT."""
    diffs = diffs or {}
    n, m = len(compiled), len(gold)
    sim = [[similarity(c, g, diffs.get(g.n)) for g in gold] for c in compiled]
    best = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            take = sim[i][j] + best[i + 1][j + 1] if sim[i][j] >= MATCH_AT else 0.0
            best[i][j] = max(take, best[i + 1][j], best[i][j + 1])
    pairs, i, j = [], 0, 0
    while i < n and j < m:
        if sim[i][j] >= MATCH_AT and abs(best[i][j] - (sim[i][j] + best[i + 1][j + 1])) < 1e-9:
            pairs.append((i, j, sim[i][j]))
            i, j = i + 1, j + 1
        elif best[i][j] == best[i + 1][j]:
            i += 1
        else:
            j += 1
    return pairs


def _seconds(t: str) -> float:
    out = 0.0
    for part in t.split(":"):
        out = out * 60 + float(part)
    return out


def _span(t: Optional[str]) -> Optional[tuple[float, float]]:
    if not t:
        return None
    a, _, b = t.partition("-")
    return _seconds(a), _seconds(b or a)


def _all_typed(steps: list[Step]) -> str:
    return _squeeze("".join(_value(s) for s in steps if s.action == "type"))


@dataclass
class Numbers:
    gold_steps: int = 0
    compiled_steps: int = 0
    matched: int = 0
    recall: float = 0.0
    precision: float = 0.0
    f1: float = 0.0
    missed: list[int] = field(default_factory=list)      # gold step numbers nothing matched
    extra: list[int] = field(default_factory=list)       # compiled step numbers that match nothing

    def line(self) -> str:
        return (f"{self.matched} matched of {self.gold_steps} gold, {self.compiled_steps} compiled: "
                f"recall {self.recall:.2f}, precision {self.precision:.2f}, F1 {self.f1:.2f}")


def _numbers(compiled, gold, pairs, *, ignore_gold=(), ignore_compiled=()) -> Numbers:
    hit_g = {j for _, j, _ in pairs}
    hit_c = {i for i, _, _ in pairs}
    credited = [j for j in hit_g]
    g_total = len(gold) - sum(1 for j, g in enumerate(gold) if g.n in ignore_gold and j not in hit_g)
    c_total = len(compiled) - sum(1 for i, c in enumerate(compiled) if c.n in ignore_compiled and i not in hit_c)
    m = len(credited)
    r = m / g_total if g_total else 0.0
    p = m / c_total if c_total else 0.0
    return Numbers(gold_steps=g_total, compiled_steps=c_total, matched=m, recall=r, precision=p,
                   f1=2 * r * p / (r + p) if r + p else 0.0,
                   missed=[g.n for j, g in enumerate(gold) if j not in hit_g and g.n not in ignore_gold],
                   extra=[c.n for i, c in enumerate(compiled) if i not in hit_c and c.n not in ignore_compiled])


def _details(compiled: list[Step], gold: list[Step], pairs, diffs: dict[int, dict]) -> dict:
    """Among matched steps: action, label, typed text, check, verify, source time, suggested values."""
    out: dict = {"action": 0, "label": 0, "typed_exact": 0, "typed_ratio": 0.0, "typed": 0, "check": 0.0,
                 "verify_kind": 0, "verify_gold": 0, "source_time": 0, "source_gold": 0, "suggested_marked": 0,
                 "suggested_gold": 0}
    for i, j, _ in pairs:
        c, g = compiled[i], gold[j]
        d = diffs.get(g.n, {})
        out["action"] += c.action == g.action or c.action in d.get("actions", [])
        out["label"] += label_score(c, g, d.get("labels")) >= 0.5
        out["check"] += _overlap(c.check, g.check)
        if g.action == "type":
            out["typed"] += 1
            vc, vg = _squeeze(_value(c)), _squeeze(_value(g))
            out["typed_exact"] += vc == vg
            out["typed_ratio"] += difflib.SequenceMatcher(None, vc, vg, autojunk=False).ratio()
        if g.verify:
            out["verify_gold"] += 1
            kinds = lambda s: {k for k in ("uia", "file") if s.verify and getattr(s.verify, k) is not None}
            out["verify_kind"] += bool(kinds(c) & kinds(g))
        sg, sc = _span(g.source.t), _span(c.source.t)
        if sg:
            out["source_gold"] += 1
            out["source_time"] += bool(sc and sc[0] <= sg[1] + SOURCE_SLACK_S and sg[0] <= sc[1] + SOURCE_SLACK_S)
        if "suggested" in g.params:
            out["suggested_gold"] += 1
            out["suggested_marked"] += "suggested" in c.params
    n = len(pairs) or 1
    typed = out["typed"] or 1
    return {
        "action": round(out["action"] / n, 3), "label": round(out["label"] / n, 3), "check_words": round(out["check"] / n, 3),
        "typed_steps": out["typed"], "typed_exact": round(out["typed_exact"] / typed, 3),
        "typed_ratio": round(out["typed_ratio"] / typed, 3),
        "verify_same_kind": f"{out['verify_kind']}/{out['verify_gold']}",
        "source_time": f"{out['source_time']}/{out['source_gold']}",
        "suggested_marked": f"{out['suggested_marked']}/{out['suggested_gold']}",
    }


def differences_path(gold_path: Path) -> Path:
    return gold_path.with_name(gold_path.stem + ".differences.yaml")


def load_differences(gold_path: Path) -> Optional[dict]:
    p = differences_path(gold_path)
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else None


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def score(compiled: Tutorial, gold: Tutorial, *, differences: Optional[dict] = None) -> dict:
    """The score as plain data. `fair` only when the gold file has a differences list."""
    pairs = align(compiled.steps, gold.steps)
    raw = _numbers(compiled.steps, gold.steps, pairs)
    both_typed = difflib.SequenceMatcher(None, _all_typed(compiled.steps), _all_typed(gold.steps), autojunk=False).ratio()
    result = {
        "raw": raw.__dict__ | {"line": raw.line()},
        "details": _details(compiled.steps, gold.steps, pairs, {}),
        "all_typed_text": round(both_typed, 3),      # every typed character, whichever steps it's split across
        "verify_share": round(sum(1 for s in compiled.steps if s.verify) / (len(compiled.steps) or 1), 3),
        "pairs": [[compiled.steps[i].n, gold.steps[j].n, round(s, 2)] for i, j, s in pairs],
    }
    if differences:
        diffs = {d["step"]: d for d in differences.get("differences", [])}
        fair_pairs = align(compiled.steps, gold.steps, diffs)
        matched_g = {gold.steps[j].n for _, j, _ in fair_pairs}
        ignore_g = {n for n, d in diffs.items() if d.get("missing_ok")}
        ignore_c = set()
        for i, j, _ in fair_pairs:          # a neighbour the list allows isn't an extra step
            d = diffs.get(gold.steps[j].n, {})
            kind = (d.get("extra_ok") or {}).get("action")
            for k in (i - 1, i + 1):
                if kind and 0 <= k < len(compiled.steps) and compiled.steps[k].action == kind:
                    ignore_c.add(compiled.steps[k].n)
        fair = _numbers(compiled.steps, gold.steps, fair_pairs, ignore_gold=ignore_g, ignore_compiled=ignore_c)
        result["fair"] = fair.__dict__ | {"line": fair.line()}
        result["fair_details"] = _details(compiled.steps, gold.steps, fair_pairs, diffs)
        result["fair_applied"] = sorted(n for n in diffs if n in matched_g or n in ignore_g)
        result["targets"] = differences.get("targets")
    return result


def find_gold(url: Optional[str], folder: Optional[Path] = None) -> Optional[Path]:
    """The gold file for a source, by its URL."""
    if not url:
        return None
    for p in sorted(Path(folder or config.TUTORIALS).glob("*.md")):
        try:
            t = parse_file(p)
        except Exception:
            continue
        if t.meta.gold and t.meta.source.url and t.meta.source.url.rstrip("/") == url.rstrip("/"):
            return p
    return None


def score_files(compiled_path, gold_path) -> dict:
    gold_path = Path(gold_path)
    diff = load_differences(gold_path)
    s = score(parse_file(compiled_path), parse_file(gold_path), differences=diff)
    s["gold_file"] = gold_path.name
    s["gold_sha"] = _sha(gold_path)
    if diff:
        s["differences_sha"] = _sha(differences_path(gold_path))
    return s


def report(s: dict) -> str:
    out = [f"raw:   {s['raw']['line']}"]
    if "fair" in s:
        out.append(f"fair:  {s['fair']['line']}   (applied to gold steps {s['fair_applied']})")
    d = s["details"]
    out.append(f"among matched: action {d['action']:.2f}, label {d['label']:.2f}, check words {d['check_words']:.2f}, "
               f"source time {d['source_time']}, verify kind {d['verify_same_kind']}, suggested marked {d['suggested_marked']}")
    if d["typed_steps"]:
        out.append(f"typed: exact {d['typed_exact']:.2f}, closeness {d['typed_ratio']:.2f} over {d['typed_steps']} steps; "
                   f"all typed text {s['all_typed_text']:.2f}")
    out.append(f"verify hints on {s['verify_share']:.0%} of compiled steps")
    out.append(f"missed gold steps: {s['raw']['missed']}   extra compiled steps: {s['raw']['extra']}")
    out.append(f"against {s['gold_file']} ({s['gold_sha']})")
    return "\n".join(out)
