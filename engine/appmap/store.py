"""App maps, two layers:

  built-in  appmaps/<app>-<version>.yaml in the repo     docs facts only: aliases, menu paths, shortcuts, sources
  local     %APPDATA%/GhostGuide/appmaps/<same name>      learned positions (`seen`, window-relative) + new apps

Reads local first, then built-in, field by field, so a learned position sits next to the docs facts for the same
control. Writes only ever go to the local layer; the built-in layer changes only when someone promotes reviewed
entries (`python -m engine appmap promote`), which copies docs facts and never positions.

Version: `vscode-1.14x.yaml` covers 1.140–1.149. The file for an app is picked by slug and the closest version
pattern; without a version the newest file for the slug wins.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from engine import config
from engine.schema.appmap import AppMap, Control, Seen

# Apps by the name tutorials use (meta.app) → file slug.
SLUGS = {"visual studio code": "vscode", "vs code": "vscode", "solidworks": "solidworks"}
DOCS_FIELDS = ("aliases", "menu_path", "shortcut", "source", "where")


def slug(app: str) -> str:
    a = app.strip().casefold()
    for k, v in SLUGS.items():
        if k in a:
            return v
    return re.sub(r"[^a-z0-9]+", "-", a).strip("-") or "app"


def local_dir() -> Path:
    if config.env("GG_LOCAL_APPMAPS"):
        return Path(config.env("GG_LOCAL_APPMAPS"))
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / "GhostGuide" / "appmaps"


def version_pattern(version: str) -> str:
    """1.143.1 → 1.14x: one built-in file per ten minor versions (docs facts rarely change faster)."""
    parts = version.split(".")
    if len(parts) < 2 or not parts[1].isdigit():
        return version
    return f"{parts[0]}.{parts[1][:-1] or '0'}x"


def _version_key(name: str) -> tuple:
    return tuple(int(x) if x.isdigit() else -1 for x in re.findall(r"\d+|x", name))


def pick_file(folder: Path, app_slug: str, version: Optional[str] = None) -> Optional[Path]:
    """`<slug>-<pattern>.yaml` whose pattern matches the version (x = any digit), else the newest one, else
    `<slug>.yaml`. None when the folder has nothing for the app."""
    files = sorted(folder.glob(f"{app_slug}-*.yaml"), key=lambda p: _version_key(p.stem))
    if version:
        for p in files:
            pat = p.stem[len(app_slug) + 1:]
            rx = "^" + re.escape(pat).replace("x", r"\d") + r"(\D|$)"
            if re.match(rx, version):
                return p
    if files:
        return files[-1]
    plain = folder / f"{app_slug}.yaml"
    return plain if plain.exists() else None


class AppMapStore:
    def __init__(self, app: str, version: Optional[str] = None, builtin_dir: Optional[Path] = None,
                 local: Optional[Path] = None):
        self.slug = slug(app)
        self.version = version
        self.builtin_dir = builtin_dir or config.APPMAPS
        self.local_dir = local or local_dir()
        self.builtin_path = pick_file(self.builtin_dir, self.slug, version)
        name = (self.builtin_path.name if self.builtin_path else
                f"{self.slug}-{version_pattern(version)}.yaml" if version else f"{self.slug}.yaml")
        self.local_path = self.local_dir / name
        self.builtin = _load(self.builtin_path)
        self.local = _load(self.local_path)

    # ---------- reading (local first) ----------
    def get(self, label: str) -> Optional[Control]:
        """The control as both layers know it: each field from the local layer when it has one."""
        lo, bi = self.local.get(label), self.builtin.get(label)
        if lo is None and bi is None:
            return None
        if lo is None or bi is None:
            return lo or bi
        merged = bi.model_dump()
        for k, v in lo.model_dump().items():
            if v not in (None, []):
                merged[k] = v
        return Control.model_validate(merged)

    def reviewed_route(self, label: str) -> Optional[list[str]]:
        """The built-in layer's route: someone clicked it on this version, so it beats what an old tutorial says."""
        c = self.builtin.get(label)
        return list(c.menu_path) if c is not None and c.menu_path else None

    def reviewed_where(self, label: str) -> Optional[str]:
        """The built-in layer's description of where a control is and what it looks like, for icons with no text."""
        c = self.builtin.get(label)
        return c.where if c is not None else None

    def names(self, label: str) -> list[str]:
        """The label and its aliases, for the UIA stage."""
        c = self.get(label)
        return [label] + (list(c.aliases) if c else [])

    # ---------- writing (local only) ----------
    def learn(self, label: str, window: str, box: tuple[int, int, int, int], win_rect: tuple[int, int, int, int],
              look: Optional[list[int]] = None) -> bool:
        """Save where a control was when its step was checked done, relative to its window, so it survives
        moving the window. Returns False when the box isn't inside the window (nothing saved)."""
        bx, by, bw, bh = box
        wx, wy, ww, wh = win_rect
        if ww <= 0 or wh <= 0 or bx < wx or by < wy or bx + bw > wx + ww or by + bh > wy + wh:
            return False
        rel = (round((bx - wx) / ww, 4), round((by - wy) / wh, 4), round(bw / ww, 4), round(bh / wh, 4))
        c = self.local.root.get(label) or Control()
        c.seen = Seen(window=window, rel_box=rel, look=look)
        self.local.root[label] = c
        self.save_local()
        return True

    def forget_seen(self, label: str) -> None:
        """Where it was remembered to be has been shown wrong."""
        c = self.local.root.get(label)
        if c is not None and c.seen is not None:
            c.seen = None
            self.save_local()

    def add_facts(self, label: str, **facts) -> None:
        """Docs facts for a control (compile-time enrich, or by hand), into the local layer."""
        c = self.local.root.get(label) or Control()
        for k, v in facts.items():
            if k in DOCS_FIELDS and v is not None:
                setattr(c, k, v)
        self.local.root[label] = c
        self.save_local()

    def save_local(self) -> None:
        self.local_dir.mkdir(parents=True, exist_ok=True)
        self.local.dump(self.local_path)

    # ---------- reviewing → built-in ----------
    def reviewable(self) -> dict[str, dict]:
        """Local entries with docs facts the built-in layer doesn't have yet (what promote would copy)."""
        out = {}
        for label, c in self.local.root.items():
            facts = {k: getattr(c, k) for k in DOCS_FIELDS if getattr(c, k) not in (None, [])}
            have = self.builtin.root.get(label)
            new = {k: v for k, v in facts.items() if have is None or getattr(have, k) != v}
            if new:
                out[label] = new
        return out

    def promote(self, labels: list[str], target: Optional[Path] = None) -> Path:
        """Copy reviewed docs facts (never `seen`) from the local layer into the built-in file."""
        default = f"{self.slug}-{version_pattern(self.version)}.yaml" if self.version else f"{self.slug}.yaml"
        target = target or self.builtin_path or (self.builtin_dir / default)
        for label in labels:
            c = self.local.root.get(label)
            if c is None:
                raise KeyError(f"{label!r} isn't in the local app map")
            have = self.builtin.root.get(label) or Control()
            for k in DOCS_FIELDS:
                v = getattr(c, k)
                if v not in (None, []):
                    setattr(have, k, v)
            have.seen = None
            self.builtin.root[label] = have
        target.parent.mkdir(parents=True, exist_ok=True)
        self.builtin.dump(target)
        self.builtin_path = target
        return target


def _load(path: Optional[Path]) -> AppMap:
    if path is None or not path.exists():
        return AppMap({})
    return AppMap.load(path)
