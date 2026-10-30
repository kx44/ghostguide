"""python -m engine validate|compile|play|eval|record"""
from __future__ import annotations

import argparse
import glob
import sys

from engine import config


def cmd_validate(args) -> int:
    from engine.basefile.validate import validate_file

    paths = sorted({p for pattern in args.paths for p in (glob.glob(pattern) or [pattern])})
    if not paths:
        print("no files given", file=sys.stderr)
        return 2
    failed = 0
    for path in paths:
        r = validate_file(path)
        status = "ok  " if r.ok else "FAIL"
        print(f"{status} {path} ({r.steps} steps, {len(r.errors)} errors, {len(r.warnings)} warnings)")
        for e in r.errors:
            print(f"     error: {e}")
        for w in r.warnings:
            print(f"     warn:  {w}")
        failed += not r.ok
    return 1 if failed else 0


def cmd_record(args) -> int:
    """One small Spark call through the client, so it can be replayed offline afterwards."""
    from engine.models.client import ModelClient

    client = ModelClient(mode=args.mode)
    reply = client.chat(
        model=args.model,
        messages=[{"role": "user", "content": args.prompt}],
        max_tokens=args.max_tokens,
        tag="cli-record",
    )
    print(f"mode={client.mode} model={args.model} cost=${reply.cost_usd:.6f} cached={reply.from_cassette}")
    print(f"cassette: {reply.cassette_key}")
    print(reply.text)
    print(f"total logged spend: ${client.spent_usd():.4f} of ${client.budget_usd:.2f}")
    return 0


def cmd_spend(args) -> int:
    from engine.models.client import ModelClient

    c = ModelClient()
    print(f"spent ${c.spent_usd():.4f} of ${c.budget_usd:.2f} (log: {config.COST_LOG})")
    return 0


def _later(phase: int):
    def run(args) -> int:
        print(f"`{args.cmd}` arrives in phase {phase} (see 05 Architecture, Build phases).", file=sys.stderr)
        return 2
    return run


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m engine")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="check base .md files against the schema and rules")
    v.add_argument("paths", nargs="+")
    v.set_defaults(func=cmd_validate)

    r = sub.add_parser("record", help="make one model call (records it in record mode, replays it in replay mode)")
    r.add_argument("--model", default=config.SPARK)
    r.add_argument("--prompt", default="Reply with exactly: GhostGuide ready.")
    r.add_argument("--max-tokens", type=int, default=16)
    r.add_argument("--mode", choices=config.MODEL_MODES, default=None, help="overrides MODEL_MODE")
    r.set_defaults(func=cmd_record)

    s = sub.add_parser("spend", help="show logged model spend against the budget cap")
    s.set_defaults(func=cmd_spend)

    for name, phase in (("play", 2), ("compile", 5), ("eval", 5)):
        p = sub.add_parser(name, help=f"phase {phase}")
        p.add_argument("rest", nargs="*")
        p.set_defaults(func=_later(phase))

    args = ap.parse_args(argv)
    from engine.dpi import make_dpi_aware
    make_dpi_aware()
    return args.func(args)
