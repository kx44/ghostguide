"""Plain text → evidence: a pasted forum answer, a README. No images, so targets are found by label alone."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Optional

from engine.compile.timeline import Evidence, Item

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


def slug(text: str) -> str:
    return "#" + (re.sub(r"[^a-z0-9]+", "-", text.casefold()).strip("-") or "section")


def from_text(text: str, url: Optional[str] = None, title: Optional[str] = None) -> Evidence:
    items, anchor = [], "#start"
    for block in re.split(r"\n\s*\n", text.replace("\r\n", "\n")):
        block = block.strip()
        if not block:
            continue
        lines = block.splitlines()
        heading = HEADING_RE.match(lines[0])
        if heading:
            anchor = slug(heading.group(2))
            items.append(Item("heading", heading.group(2).strip(), anchor=anchor))
            block = "\n".join(lines[1:]).strip()
            if not block:
                continue
        items.append(Item("text", block, anchor=anchor))
    if not items:
        from engine.compile.adapters import SourceError
        raise SourceError("That text is empty.")
    body = "\n".join(i.text for i in items)
    return Evidence(type="text", hash=hashlib.sha256(body.encode()).hexdigest()[:16], items=items, url=url,
                    title=title or next((i.text for i in items if i.kind == "heading"), None))


def from_file(path: Path) -> Evidence:
    return from_text(Path(path).read_text(encoding="utf-8", errors="replace"), title=Path(path).stem)
