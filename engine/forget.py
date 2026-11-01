"""What this PC holds for GhostGuide, and taking it away (`python -m engine forget`). Only these folders are ever touched.
The spend log stays, because the budget cap adds it up, and so do the tutorial files, which are yours."""
from __future__ import annotations

import os
import stat
from pathlib import Path

from engine import config
from engine.appmap.store import local_dir
from engine.live import source

COST_LOG_NAME = config.COST_LOG.name
kept: list[Path] = []      # what `remove` couldn't take, because something still has it open


def _places() -> list[tuple[str, Path]]:
    c = config.CACHE
    return [("Where you stopped in each tutorial", c / "sessions"),
            ("Tutorial sources kept for the source view: clips and readings", source.STORE),
            ("What compiling read: frames and text of the tutorials", c / "compiled"),
            ("Recorded model answers (no pictures in them)", config.CASSETTES),
            ("Hand-pinned boxes", c / "pins"),
            ("Logs, apart from the spend log", config.LOGS),
            ("Screenshots from the checks in tests/", c / "screenshots"),
            ("Where this app's buttons were on this PC: positions and tiny grey thumbnails", local_dir()),
            *(("The overlay's browser data: pictures from web pages it showed, and its caches", p) for p in _overlay_data())]


def _overlay_data() -> list[Path]:
    """Electron's own folder: named after the package when run from source, after the product when built, where it shares a
    folder with the app maps and the settings."""
    base = Path(os.environ.get("APPDATA") or Path.home() / ".config")
    built = base / "GhostGuide"
    return [base / "ghostguide-overlay", *(built / name for name in ("Cache", "Code Cache", "Network", "Local Storage", "Session Storage"))]


def _is_link(p: Path) -> bool:
    """A symbolic link or a junction: remove the link, never what it points at."""
    st = os.lstat(p)
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _size(p: Path) -> int:
    if not p.exists():
        return 0
    total = 0
    for root, dirs, files in os.walk(p):         # os.walk doesn't go into a link to a folder
        dirs[:] = [d for d in dirs if not _is_link(Path(root) / d)]
        for f in files:
            fp = Path(root) / f
            if f != COST_LOG_NAME and not _is_link(fp):
                total += fp.stat().st_size
    return total


def holdings() -> list[dict]:
    return [{"what": what, "path": str(p), "bytes": _size(p)} for what, p in _places() if p.exists()]


def remove(folder: Path) -> None:
    """Everything in the folder but the spend log. A link goes as a link: what it points at stays where it is."""
    for entry in list(folder.iterdir()):
        try:
            if _is_link(entry):
                os.rmdir(entry) if entry.is_dir() else entry.unlink()
            elif entry.is_dir():
                remove(entry)
                if not any(entry.iterdir()):
                    entry.rmdir()
            elif entry.name != COST_LOG_NAME:
                entry.unlink()
        except PermissionError:     # a file a running overlay or engine holds open: the rest still goes
            kept.append(entry)
