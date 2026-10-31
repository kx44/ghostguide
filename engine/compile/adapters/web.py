"""Web page → evidence: the main text with its images in place. A link, or a page someone saved from their browser.

A site that refuses automatic reading gets a clear message and an offer to use a saved copy. We ask once, as ourselves,
and don't retry in disguise.
"""
from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass, field
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import unquote, urljoin, urlparse

from engine.compile.adapters import SourceBlocked, SourceError
from engine.compile.adapters.text import slug
from engine.compile.timeline import Evidence, Item

SKIP = {"script", "style", "noscript", "nav", "footer", "aside", "form", "svg", "iframe", "template", "header", "button"}
BLOCKS = {"p", "li", "pre", "blockquote", "td", "figcaption", "dd", "dt"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
VOID = {"img", "br", "hr", "meta", "link", "input", "source", "area", "base", "col", "embed", "param", "track", "wbr"}
CONTAINERS = {"article", "main", "section", "div"}
MAIN_SHARE = 0.6            # the main part: the deepest element holding at least this much of the page's paragraphs
MIN_IMAGE_SIDE = 200        # logos and icons aren't evidence
MAX_IMAGE_W = 1280
USER_AGENT = "GhostGuide/0.1 (tutorial importer)"
CHALLENGE = ("just a moment", "performing security verification", "verify you are human", "enable javascript and cookies")


@dataclass
class _Block:
    kind: str                       # heading | text | image
    text: str
    path: tuple[int, ...]           # ids of the containers it sits in
    src: Optional[str] = None
    anchor: Optional[str] = None


@dataclass
class _Page:
    blocks: list[_Block] = field(default_factory=list)
    title: Optional[str] = None
    canonical: Optional[str] = None
    author: Optional[str] = None
    published: Optional[str] = None


class _Reader(HTMLParser):
    """Flat list of blocks, each knowing which containers it's inside; picks nothing yet."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.page = _Page()
        self.stack: list[tuple[str, int]] = []
        self.next_id = 0
        self.skip_depth = 0
        self.buf: list[str] = []
        self.open_block: Optional[tuple[str, Optional[str]]] = None
        self.in_title = False
        self.title_buf: list[str] = []

    def _path(self) -> tuple[int, ...]:
        return tuple(i for tag, i in self.stack if tag in CONTAINERS)

    def _flush(self) -> None:
        if self.open_block is None:
            return
        text = re.sub(r"[ \t\r\f\v]+", " ", "".join(self.buf)) if self.open_block[0] != "pre" else "".join(self.buf)
        text = re.sub(r"\n\s*\n+", "\n", text).strip()
        tag, anchor = self.open_block
        self.open_block, self.buf = None, []
        if not text:
            return
        if tag in HEADINGS:
            self.page.blocks.append(_Block("heading", text, self._path(), anchor=anchor and f"#{anchor}"))
        else:
            self.page.blocks.append(_Block("text", f"- {text}" if tag == "li" else text, self._path()))

    def handle_starttag(self, tag, attrs):
        a = {k: v or "" for k, v in attrs}
        if tag == "title":
            self.in_title = True
        elif tag == "link" and a.get("rel") == "canonical":
            self.page.canonical = a.get("href") or None
        elif tag == "meta":
            name = (a.get("property") or a.get("name") or "").casefold()
            if name == "article:published_time":
                self.page.published = a.get("content", "")[:10] or None
            elif name == "author":
                self.page.author = a.get("content") or None
        if tag in VOID:
            if tag == "img" and not self.skip_depth:
                src = a.get("src") or a.get("data-src") or ""
                if src:
                    self._flush()
                    self.page.blocks.append(_Block("image", a.get("alt", "").strip(), self._path(), src=src))
            elif tag == "br" and self.open_block:
                self.buf.append("\n")
            return
        if tag in SKIP:
            self.skip_depth += 1
        if not self.skip_depth and (tag in BLOCKS or tag in HEADINGS):
            self._flush()
            self.open_block = (tag, a.get("id"))
        self.stack.append((tag, self.next_id))
        self.next_id += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
            self.page.title = re.sub(r"\s+", " ", "".join(self.title_buf)).strip() or None
        if tag in VOID:
            return
        if not any(t == tag for t, _ in self.stack):
            return
        if not self.skip_depth and (tag in BLOCKS or tag in HEADINGS or (self.open_block and tag in CONTAINERS)):
            self._flush()
        while self.stack:
            t, _ = self.stack.pop()
            if t in SKIP:
                self.skip_depth -= 1
            if t == tag:
                break

    def handle_data(self, data):
        if self.in_title:
            self.title_buf.append(data)
        elif not self.skip_depth and self.open_block is not None:
            self.buf.append(data)


def read_page(html: str) -> _Page:
    r = _Reader()
    r.feed(html)
    r._flush()
    return r.page


def main_blocks(page: _Page) -> list[_Block]:
    """The blocks inside the main part of the page: the deepest container holding most of the paragraph text."""
    size: dict[int, int] = {}
    total = 0
    for b in page.blocks:
        if b.kind == "text":
            total += len(b.text)
            for c in b.path:
                size[c] = size.get(c, 0) + len(b.text)
    if not total:
        return [b for b in page.blocks if b.kind != "image"]
    best = None
    for b in page.blocks:
        for depth, c in enumerate(b.path):
            if size.get(c, 0) >= MAIN_SHARE * total and (best is None or depth > best[0]):
                best = (depth, c)
    return [b for b in page.blocks if best is None or best[1] in b.path]


def looks_blocked(status: int, html: str) -> bool:
    if status in (401, 403, 429, 503):
        return True
    head = html[:6000].casefold()
    return any(c in head for c in CHALLENGE)


def fetch_page(url: str) -> str:
    import httpx

    host = urlparse(url).netloc
    try:
        r = httpx.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30)
    except httpx.HTTPError as e:
        raise SourceError(f"Couldn't reach {host} ({e.__class__.__name__}). Check the link, or save the page "
                          "from your browser and drop the file here.") from e
    if looks_blocked(r.status_code, r.text):
        raise SourceBlocked(f"{host} doesn't allow automatic reading. Open the page in your browser, save it "
                            "(Save as → Webpage, Complete) and drop the file here.")
    if r.status_code != 200:
        raise SourceError(f"{host} answered {r.status_code} for that link.")
    return r.text


def to_jpeg(data: bytes, max_w: int = MAX_IMAGE_W) -> Optional[bytes]:
    """Re-encoded and capped in size, or None for what's too small to be evidence or can't be read."""
    from PIL import Image

    try:
        im = Image.open(io.BytesIO(data))
        im.load()
    except Exception:
        return None
    if min(im.size) < MIN_IMAGE_SIDE:
        return None
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)))
    out = io.BytesIO()
    im.convert("RGB").save(out, "JPEG", quality=80)
    return out.getvalue()


def _local_loader(html_path: Path) -> Callable[[str], Optional[bytes]]:
    def load(src: str) -> Optional[bytes]:
        if src.startswith(("http:", "https:", "data:")):
            return None     # a saved page keeps what it needs beside it; nothing more is fetched
        p = (html_path.parent / unquote(src.split("?")[0])).resolve()
        return p.read_bytes() if p.is_file() else None
    return load


def _web_loader(base: str) -> Callable[[str], Optional[bytes]]:
    import httpx

    def load(src: str) -> Optional[bytes]:
        if src.startswith("data:"):
            return None
        try:
            r = httpx.get(urljoin(base, src), headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=30)
        except httpx.HTTPError:
            return None
        return r.content if r.status_code == 200 else None
    return load


def from_html(html: str, url: Optional[str], load_image: Callable[[str], Optional[bytes]]) -> Evidence:
    if looks_blocked(200, html):
        raise SourceBlocked("That file is the site's security check, not the article. Wait for the article to "
                            "appear in your browser, then save it again.")
    page = read_page(html)
    items: list[Item] = []
    anchor = "#start"
    seen_h: set[str] = set()
    digest = hashlib.sha256()
    for b in main_blocks(page):
        if b.kind == "heading":
            anchor = b.anchor or slug(b.text)
            if anchor in seen_h:
                anchor = f"{anchor}-{len(seen_h)}"
            seen_h.add(anchor)
            items.append(Item("heading", b.text, anchor=anchor))
            digest.update(b.text.encode())
        elif b.kind == "text":
            items.append(Item("text", b.text, anchor=anchor))
            digest.update(b.text.encode())
        else:
            data = load_image(b.src or "")
            jpeg = to_jpeg(data) if data else None
            if jpeg:
                items.append(Item("image", b.text, anchor=anchor, image=jpeg))
                digest.update(jpeg)
    if not any(i.kind == "text" for i in items):
        raise SourceError("No readable article text on that page. Paste the text here instead.")
    title = unescape(page.title).strip() if page.title else None
    return Evidence(type="web", hash=digest.hexdigest()[:16], items=items, url=url or page.canonical, title=title,
                    author=page.author, published=page.published)


def from_url(url: str) -> Evidence:
    return from_html(fetch_page(url), url, _web_loader(url))


def from_file(path: Path) -> Evidence:
    path = Path(path)
    return from_html(path.read_text(encoding="utf-8", errors="replace"), None, _local_loader(path))
