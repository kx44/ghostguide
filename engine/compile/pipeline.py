"""Compile a tutorial, once: read the source, build the timeline, pass 1, pass 2, enrich,
validate, save, score. A source compiled before with the same prompts and model opens from the cache for free.

    python -m engine compile "https://www.youtube.com/watch?v=…" --start 01:28 --end 10:25
    python -m engine compile saved-article.html
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from engine import config
from engine.appmap.store import AppMapStore
from engine.basefile.parse import parse_file
from engine.basefile.render import render_file
from engine.basefile.validate import validate_file
from engine.compile import eval as evaluate
from engine.compile.adapters import SourceError, text as text_adapter, video, web
from engine.compile.enrich import enrich
from engine.compile.passes import CompileError, prompts_version
from engine.compile.passes.extract import extract
from engine.compile.passes.merge import merge
from engine.compile.timeline import Evidence, Item, segments
from engine.models.client import ModelClient

CACHE = config.CACHE / "compiled"
SCORES = config.LOGS / "scores.jsonl"
VIDEO_HOSTS = re.compile(r"^https?://([\w-]+\.)?(youtube\.com|youtu\.be|vimeo\.com)/", re.I)
VIDEO_FILES = (".mp4", ".mkv", ".webm", ".mov", ".avi")
TEXT_FILES = (".txt", ".md")
WEB_FILES = (".html", ".htm")

# Share of the progress bar each stage ends at.
STAGES = {"read": 0.25, "extract": 0.65, "merge": 0.88, "enrich": 0.96, "save": 1.0}


@dataclass
class Options:
    start: Optional[str] = None
    end: Optional[str] = None
    narration: str = "auto"       # auto (captions, then Transcribe) | captions | transcribe
    max_frames: int = 150
    model: Optional[str] = None
    enrich: bool = True
    fresh: bool = False
    out: Optional[Path] = None
    gold: Optional[Path] = None
    version: Optional[str] = None


@dataclass
class Result:
    path: Path
    title: str
    steps: int
    model: str
    source_hash: str
    cached: bool = False
    cost_usd: float = 0.0
    score: Optional[dict] = None
    enrich: Optional[dict] = None
    warnings: list[str] = field(default_factory=list)


Progress = Callable[[str, float], None]


def _save_evidence(ev: Evidence, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    items = []
    for n, item in enumerate(ev.items):
        name = None
        if item.image is not None:
            name = f"i{n:04d}.jpg"
            (folder / name).write_bytes(item.image)
        items.append(item.to_wire(name))
    data = {k: getattr(ev, k) for k in ("type", "hash", "url", "title", "author", "published", "segment", "notes")}
    (folder / "evidence.json").write_text(json.dumps({**data, "items": items}, ensure_ascii=False), encoding="utf-8")


def _load_evidence(folder: Path) -> Optional[Evidence]:
    p = folder / "evidence.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    items = []
    for i in d.pop("items"):
        name = i.pop("image", None)
        items.append(Item(**i, image=(folder / name).read_bytes() if name else None))
    return Evidence(items=items, **d)


def read_source(src: str, opts: Options, client: ModelClient, note: Callable[[str], None] = lambda s: None) -> Evidence:
    """Picks the adapter. `src` is a link, a file, or pasted text. A video's reading is kept, so a retune doesn't
    download and cut it again and its frames stay byte-identical (which is what lets recorded replies replay)."""
    is_url = src.startswith(("http://", "https://"))
    if is_url and not VIDEO_HOSTS.match(src):
        return web.from_url(src)
    path = None
    if not is_url:
        try:
            p = Path(src)
            path = p if len(src) < 500 and p.is_file() else None
        except OSError:
            path = None
        if path is None:
            if "\n" not in src.strip() and len(src) < 300:
                raise SourceError(f"Can't find a file or link called {src[:80]}.")
            return text_adapter.from_text(src)
        suffix = path.suffix.casefold()
        if suffix in WEB_FILES:
            return web.from_file(path)
        if suffix in TEXT_FILES:
            return text_adapter.from_file(path)
        if suffix not in VIDEO_FILES:
            raise SourceError(f"Can't read {suffix or 'that kind of'} files yet: use a link, a video, a saved web page or text.")

    who = src if is_url else path.name
    key = hashlib.sha256(f"{who}|{opts.start}|{opts.end}|{opts.max_frames}|{opts.narration}".encode()).hexdigest()[:16]
    folder = CACHE / "evidence" / key
    ev = None if opts.fresh else _load_evidence(folder)
    if ev is not None:
        note("Using the video already read")
        return ev
    if is_url:
        ev = video.from_url(src, client=client, start=opts.start, end=opts.end, narration=opts.narration,
                            max_frames=opts.max_frames, progress=note)
    else:
        ev = video.from_video(path, client=client, offset=video.seconds(opts.start) or 0.0, end=video.seconds(opts.end),
                              max_frames=opts.max_frames, progress=note)
    _save_evidence(ev, folder)
    return ev


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-")[:60] or "tutorial"


def compile_tutorial(src: str, opts: Optional[Options] = None, *, client: Optional[ModelClient] = None,
                     progress: Progress = lambda stage, pct: None, log=lambda s: None) -> Result:
    opts = opts or Options()
    client = client or ModelClient(mode="replay" if config.model_mode() == "replay" else "record")
    model = opts.model or config.compile_model()
    spent_at_start = client.spent_usd()

    progress("Reading the tutorial", 0.02)
    ev = read_source(src, opts, client, note=lambda s: progress(s, 0.1))
    log(f"  source: {ev.type}, {len(ev.items)} items, {ev.images} images, hash {ev.hash}" + (f"; {ev.notes}" if ev.notes else ""))

    gold = opts.gold or evaluate.find_gold(ev.url)
    key = hashlib.sha256(f"{ev.hash}|{prompts_version()}|{model}|{opts.enrich}".encode()).hexdigest()[:16]
    done_file = CACHE / f"{key}.json"
    if done_file.exists() and not opts.fresh:
        d = json.loads(done_file.read_text(encoding="utf-8"))
        if Path(d["path"]).exists():
            progress("Already compiled", 1.0)
            return Result(path=Path(d["path"]), title=d["title"], steps=d["steps"], model=model, source_hash=ev.hash,
                          cached=True, score=d.get("score"), enrich=d.get("enrich"))

    segs = segments(ev)
    log(f"  {len(segs)} segment(s), images per segment: {[s.images for s in segs]}")
    progress(f"Reading {len(segs)} part{'s' if len(segs) != 1 else ''}", STAGES["read"])
    span = STAGES["extract"] - STAGES["read"]
    raw = extract(client, model, ev, segs,
                  done=lambda n, of: progress(f"Read part {n} of {of}", STAGES["read"] + span * n / of))
    actions = sum(len(r["actions"]) for r in raw)
    log(f"  pass 1: {actions} raw actions")
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / f"{key}-raw.json").write_text(json.dumps(raw, ensure_ascii=False, indent=1), encoding="utf-8")
    if not actions:
        raise CompileError("Found no steps to follow in that source.")

    progress("Writing the steps", STAGES["extract"])
    tut = merge(client, model, ev, raw)
    log(f"  pass 2: {len(tut.steps)} steps")

    info = None
    if opts.enrich:
        progress("Looking up controls in the app's help", STAGES["merge"])
        info = enrich(client, model, tut, AppMapStore(tut.meta.app, version=opts.version), version=opts.version, log=log)
        log(f"  enrich: {info['found']} of {info['asked']} new controls, {info['searches']} searches")

    progress("Saving", STAGES["enrich"])
    tut.meta.__pydantic_extra__["compiled"] = {"model": model, "prompts": prompts_version()}
    out = opts.out or config.COMPILED / f"{gold.stem if gold else _slug(tut.meta.title)}.compiled.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    render_file(tut, out)
    check = validate_file(out)
    if not check.ok:
        raise CompileError("The saved file doesn't pass the checks:\n  " + "\n  ".join(check.errors[:12]))

    score = evaluate.score_files(out, gold) if gold else None
    result = Result(path=out, title=tut.meta.title, steps=len(tut.steps), model=model, source_hash=ev.hash,
                    cost_usd=client.spent_usd() - spent_at_start, score=score, enrich=info, warnings=check.warnings)
    done_file.parent.mkdir(parents=True, exist_ok=True)
    done_file.write_text(json.dumps({"path": str(out), "title": result.title, "steps": result.steps, "score": score,
                                     "enrich": info}, ensure_ascii=False), encoding="utf-8")
    if score:
        _log_score(result, score)
    progress("Done", 1.0)
    return parse_ok(result)


def parse_ok(result: Result) -> Result:
    """The file on disk must read back as what we mean to play."""
    parse_file(result.path)
    return result


def _log_score(result: Result, score: dict) -> None:
    """Every score ever made, so the note can show the first run beside the last."""
    SCORES.parent.mkdir(parents=True, exist_ok=True)
    row = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "file": result.path.name, "model": result.model,
           "prompts": prompts_version(), "steps": result.steps, "cost_usd": round(result.cost_usd, 4),
           "raw_f1": round(score["raw"]["f1"], 3), "fair_f1": round(score["fair"]["f1"], 3) if "fair" in score else None,
           "by_meaning_f1": round(score["by_meaning"]["f1"], 3),
           "details": score["details"], "all_typed_text": score["all_typed_text"], "verify_share": score["verify_share"],
           "gold_sha": score["gold_sha"]}
    with SCORES.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
