"""Source view: where a step came from in the original tutorial. No model calls.

A video opens at the step's `source.t`, a web page or text at its `source.anchor`. Nothing here is committed: tutorial
files only say *what* the source is, and what this PC holds is kept in the cache as the compile reads it. On a PC
that has none of it (a fresh clone), a video gets a link at the right moment, a web page gets one polite try, and a site
that refuses gets a clear message, a link and the choice of a saved copy.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

from engine import config
from engine.schema import messages as m

STORE = Path(config.env("GG_SOURCES") or config.CACHE / "sources")      # GG_SOURCES: an empty one acts like a fresh clone
LEAD_S = 1.5       # the moment before the step, for context
TAIL_S = 1.0
MIN_CLIP_S = 6.0    # a keyframe's time can be a single moment: still show the action
FETCH_TIMEOUT_S = 8
VIDEO_FILES = (".mp4", ".mkv", ".webm", ".mov", ".avi")
PAGE_FILES = (".html", ".htm", ".txt", ".md")


# ---------- what this PC holds ----------
def _index_path() -> Path:
    return STORE / "index.json"


def _read_index() -> dict:
    try:
        return json.loads(_index_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _keys(*keys: Optional[str]) -> list[str]:
    return [k for k in keys if k and k != "TBD"]


def _remember(entry: dict, *keys: Optional[str]) -> None:
    index = _read_index()
    for k in _keys(*keys):
        index[k] = entry
    STORE.mkdir(parents=True, exist_ok=True)
    _index_path().write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")


def remember_video(file: Path, offset: float, *keys: Optional[str]) -> None:
    """`offset`: where this file starts in the original video, so a step's time finds its place in it."""
    _remember({"video": str(file), "offset": offset}, *keys)


def remember_reading(ev, *keys: Optional[str]) -> None:
    """The words of a web page or text, as the compile read them: the anchors in its steps come from this reading."""
    folder = STORE / "readings" / ev.hash
    folder.mkdir(parents=True, exist_ok=True)
    blocks = []
    for n, item in enumerate(ev.items):
        block = {"kind": item.kind, "text": item.text, "anchor": item.anchor}
        if item.image is not None:
            name = f"i{n:04d}.jpg"
            (folder / name).write_bytes(item.image)
            block["image"] = name
        elif item.link:
            block["web_image"] = item.link
        blocks.append(block)
    (folder / "reading.json").write_text(json.dumps(blocks, ensure_ascii=False), encoding="utf-8")
    _remember({"reading": ev.hash}, ev.hash, ev.url, *keys)


def held(hash_: Optional[str], url: Optional[str]) -> Optional[dict]:
    index = _read_index()
    return next((index[k] for k in _keys(hash_, url) if k in index), None)


def _reading(entry: Optional[dict]) -> Optional[list[dict]]:
    if not entry or "reading" not in entry:
        return None
    folder = STORE / "readings" / entry["reading"]
    try:
        blocks = json.loads((folder / "reading.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    for b in blocks:
        if b.get("image"):
            b["image"] = (folder / b["image"]).resolve().as_uri()
        if b.get("web_image") and not (safe_link(b["web_image"]) or "").startswith("https://"):
            del b["web_image"]
    return blocks


# ---------- plain logic ----------
def clock(s: float) -> str:
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def times(t: str) -> tuple[float, Optional[float]]:
    """'01:39-01:44' or '03:40' → seconds in the original video."""
    from engine.compile.adapters.video import seconds

    first, _, last = t.partition("-")
    return seconds(first.strip()), seconds(last.strip()) if last.strip() else None


def clip_range(t: str, offset: float = 0.0) -> tuple[float, float]:
    """Start and stop in the file, whose first frame is `offset` in the original video."""
    t0, t1 = times(t)
    end = max(t1 if t1 is not None else t0, t0 + MIN_CLIP_S)
    return max(0.0, t0 - offset - LEAD_S), max(0.0, end - offset + TAIL_S)


def safe_link(url: Optional[str]) -> Optional[str]:
    """Only web links may leave for the browser: a tutorial file is someone else's text."""
    if not url:
        return None
    u = urlparse(url)
    return url if u.scheme in ("http", "https") and u.netloc else None


def video_link(url: Optional[str], t: float) -> Optional[str]:
    """The original at that moment."""
    if not safe_link(url):
        return None
    u = urlparse(url)
    s = f"{int(t)}s"
    if re.search(r"(^|\.)(youtube\.com|youtu\.be)$", u.netloc, re.I):
        q = [(k, v) for k, v in parse_qsl(u.query) if k != "t"] + [("t", s)]
        return urlunparse(u._replace(query=urlencode(q)))
    if re.search(r"(^|\.)vimeo\.com$", u.netloc, re.I):
        return urlunparse(u._replace(fragment=f"t={s}"))
    return url


def resolve_anchor(anchor: Optional[str], anchors: list[str]) -> Optional[str]:
    """The section in this reading. A hand-written file may say '#step-3' for the section '#3-draw-the-profile'."""
    if not anchor:
        return None
    if anchor in anchors:
        return anchor
    n = re.fullmatch(r"#(?:step|part|section)-?(\d+)", anchor, re.I)
    if n:
        return next((a for a in anchors if re.match(rf"#{n.group(1)}(?:\D|$)", a)), None)
    return None


def page_link(url: Optional[str], anchor: Optional[str], heading: Optional[str] = None) -> Optional[str]:
    """The page, scrolled to the section where the browser can: our anchors are made from headings, not the page's own
    ids, so this asks for the heading's words. A browser that can't find them just opens the page."""
    if not safe_link(url):
        return None
    words = heading or (re.sub(r"^#", "", anchor).replace("-", " ") if anchor else "")
    words = re.sub(r"^[\d.\s]+", "", words).strip()
    if len(words.split()) < 2 or re.fullmatch(r"(step|part|section)\s*\d*", words, re.I):
        return url
    return urlunparse(urlparse(url)._replace(fragment=":~:text=" + quote(words, safe="")))


def step_words(step) -> list[str]:
    """The names to look for in the text: a route's stops in order, then the control. "OK (green check)" is "OK"."""
    from engine.live.locate.menu import hop_label

    out: list[str] = []
    for name in [*(step.target.menu_path or []), step.target.label]:
        name = re.sub(r"\(.*?\)", "", hop_label(name)).strip()
        if len(name) >= 2 and name.casefold() not in (x.casefold() for x in out):
            out.append(name)
    return out


def figure_for(step, blocks: list[dict], anchor: Optional[str]) -> Optional[dict]:
    """The picture that goes with this step: in its section, and when the section has several, the first after the words that
    name the step's control. Authors put a picture after what it shows. Free, from the text alone, so it's a good guess."""
    section = [b for b in blocks if anchor and b.get("anchor") == anchor]
    pictures = [i for i, b in enumerate(section) if b["kind"] == "image" and (b.get("image") or b.get("web_image"))]
    if not pictures:
        return None
    at = -1
    for word in step_words(step):
        said = re.compile(rf"\b{re.escape(word)}\b", re.I)
        at = next((i for i, b in enumerate(section) if i > at and b["kind"] == "text" and said.search(b.get("text") or "")), at)
    return section[next((i for i in pictures if i > at), pictures[-1])]


def label(tut, step) -> str:
    """What the card's source button says."""
    return f"▶ {clock(times(step.source.t)[0])}" if tut.meta.source.type == "video" and step.source.t else "Source"


# ---------- the view ----------
class Sources:
    """One tutorial's source. A page that refuses is asked once per run."""

    def __init__(self, tutorial):
        self.tut = tutorial
        self.refused: Optional[str] = None
        self.asked = False
        self.to_fetch: Optional[str] = None     # a page to try outside the player's lock (the server does it)
        self._blocks: Optional[list[dict]] = None    # the reading, for the card's picture: every redraw asks

    def picture(self, step) -> Optional[str]:
        """The file address of this step's picture for its card, when this PC holds one. Never from the web: the card draws
        on every step, and only what's on this PC goes there."""
        src = self.tut.meta.source
        if src.type == "video":
            return None
        if self._blocks is None:
            self._blocks = _reading(held(src.hash, src.url)) or []
        anchors = [b["anchor"] for b in self._blocks if b.get("anchor")]
        found = figure_for(step, self._blocks, resolve_anchor(step.source.anchor, anchors))
        return found.get("image") if found else None

    def _base(self, step, of: int, follow: bool) -> dict:
        return dict(n=step.n, of=of, title=step.title, tutorial=self.tut.meta.title, follow=follow)

    def view(self, step, of: int, follow: bool = False) -> m.SourceView:
        self.to_fetch = None
        kind = self.tut.meta.source.type
        return self._video(step, of, follow) if kind == "video" else self._page(step, of, follow)

    def _video(self, step, of: int, follow: bool) -> m.SourceView:
        src = self.tut.meta.source
        base = self._base(step, of, follow)
        if not step.source.t:
            return m.SourceView(kind="none", message="The tutorial doesn't say where in the video this step is.",
                                link=safe_link(src.url), link_label="Open the video", choose="video", **base)
        t0, t1 = times(step.source.t)
        where = clock(t0) + (f"–{clock(t1)}" if t1 is not None and t1 != t0 else "")
        link = video_link(src.url, t0)
        link_label = f"Open at {clock(t0)} in the browser"
        file, offset = self._video_file()
        if file is None:
            message = ("The clip isn't on this PC. Videos aren't kept with the tutorial, and it stays the author's to host."
                       if link else "The video file isn't on this PC. Choose it to watch this step.")
            return m.SourceView(kind="none", where=where, message=message, link=link, link_label=link_label, choose="video", **base)
        start, end = clip_range(step.source.t, offset)
        return m.SourceView(kind="video", where=where, video=file.resolve().as_uri(), start=start, end=end,
                            link=link, link_label=link_label, **base)

    def _video_file(self) -> tuple[Optional[Path], float]:
        src = self.tut.meta.source
        entry = held(src.hash, src.url)
        if entry and entry.get("video") and Path(entry["video"]).is_file():
            return Path(entry["video"]), float(entry.get("offset") or 0.0)
        segment = getattr(src, "segment", None)      # a file written by hand names the same clip a compile downloads
        if src.url and segment:
            from engine.compile.adapters.video import clip_path

            lo, hi = times(str(segment))
            clip = clip_path(src.url, lo, hi, STORE)
            if clip.is_file():
                return clip, lo
        return None, 0.0

    def _page(self, step, of: int, follow: bool) -> m.SourceView:
        src = self.tut.meta.source
        base = self._base(step, of, follow)
        blocks = _reading(held(src.hash, src.url))
        if blocks is None:
            link = page_link(src.url, step.source.anchor)
            if self.refused:
                return m.SourceView(kind="none", message=self.refused, link=link, link_label="Open in the browser", choose="page", **base)
            if safe_link(src.url):
                if not self.asked:
                    self.asked, self.to_fetch = True, src.url
                return m.SourceView(kind="loading", message="Reading the page…", link=link, link_label="Open in the browser", **base)
            return m.SourceView(kind="none", message="The tutorial's text isn't on this PC. It was imported somewhere else, "
                                "and only its steps came along. Choose a copy to read it here.", choose="page", **base)
        anchors = [b["anchor"] for b in blocks if b.get("anchor")]
        anchor = resolve_anchor(step.source.anchor, anchors)
        heading = next((b["text"] for b in blocks if b["kind"] == "heading" and b.get("anchor") == anchor), None)
        note = None if anchor or not step.source.anchor else "This copy has no section matching this step, so here's the whole tutorial."
        figure = figure_for(step, blocks, anchor)
        missing = any(b.get("web_image") for b in blocks)     # a saved copy that holds its pictures would put them on the cards too
        return m.SourceView(kind="text", where=heading, doc=str(src.hash or src.url), blocks=[m.SourceBlock(**b) for b in blocks],
                            figure=m.SourceBlock(**figure) if figure else None, anchor=anchor, note=note,
                            link=page_link(src.url, step.source.anchor, heading), link_label="Open in the browser",
                            choose="page" if missing else None, **base)

    def fetch(self, url: str) -> None:
        """One try, under our own name. Runs outside the player's lock. Afterwards view() has the words or the reason."""
        from engine.compile.adapters import SourceBlocked, SourceError
        from engine.compile.adapters.web import fetch_page, from_html

        host = urlparse(url).netloc
        src = self.tut.meta.source
        try:
            ev = from_html(fetch_page(url, timeout=FETCH_TIMEOUT_S), url, lambda _: None, web_images=True)    # pictures stay on the site
            remember_reading(ev, src.hash, src.url)
        except SourceBlocked:
            self.refused = (f"This page isn't saved on this PC, and {host} doesn't allow automatic reading. "
                            "Open it in the browser, or choose a copy you saved.")
        except SourceError:
            self.refused = f"This page isn't saved on this PC, and {host} can't be reached right now."
        except Exception as e:    # a malformed link in a file, a full disk: a message, never "Reading the page…" for ever
            self.refused = f"This page isn't saved on this PC, and it couldn't be read here ({type(e).__name__})."

    def choose(self, path: str, step, of: int) -> m.SourceView:
        """A copy the person picked: a video, a saved page or a text file. Goes with this tutorial from now on."""
        p = Path(path)
        src = self.tut.meta.source
        suffix = p.suffix.casefold()
        wanted = VIDEO_FILES if src.type == "video" else PAGE_FILES
        if not p.is_file() or suffix not in wanted:
            view = self.view(step, of)
            view.note = f"That isn't a {'video' if src.type == 'video' else 'saved page or text'} file."
            return view
        if src.type == "video":
            remember_video(p, 0.0, src.hash, src.url)
            return self.view(step, of)
        from engine.compile.adapters import SourceError, text, web

        try:
            ev = web.from_file(p, web_images=True) if suffix in (".html", ".htm") else text.from_file(p)
        except SourceError as e:
            view = self.view(step, of)
            view.note = str(e)
            return view
        remember_reading(ev, src.hash, src.url)
        self.refused = None
        self._blocks = None
        return self.view(step, of)
