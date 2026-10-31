"""Which windows are on screen (live step 3): top-level windows in z-order, the front one, and the app window
a step means ("Browser" → the front Chrome / Edge / Firefox window). Plain Win32 through ctypes, no UIA, so
it's instant (a UIA walk of one window takes ~0.7 s).

Positions are physical pixels (the engine is per-monitor DPI aware). The pure helpers at the top are
unit-tested off Windows; everything that calls Win32 is below `# ---------- Windows`.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlparse

# Window-kind target labels that name a kind of app rather than a title.
APP_KINDS = {
    "browser": ("Google Chrome", "Microsoft Edge", "Mozilla Firefox", "Brave", "Opera"),
    "terminal": ("Windows PowerShell", "Command Prompt", "Terminal"),
    "file explorer": ("File Explorer",),
}
OVERLAY_TITLE = "GhostGuide overlay"
OWN_TITLE = "GhostGuide"


@dataclass
class Win:
    hwnd: int
    title: str
    rect: tuple[int, int, int, int]      # x, y, w, h (visible frame, physical px)
    minimized: bool = False

    @property
    def area(self) -> int:
        return self.rect[2] * self.rect[3]


def foreign_browser(title: str, wanted: str) -> bool:
    """A browser window that merely shows a page about the app ("… SOLIDWORKS … - Google Chrome"), when the app
    itself is what's wanted."""
    names = APP_KINDS["browser"]
    if any(n.casefold() in wanted.casefold() for n in names) or wanted.strip().casefold() == "browser":
        return False
    return any(title.casefold().endswith(n.casefold()) for n in names)


def ours(title: str, wanted: str) -> bool:
    """One of GhostGuide's own windows, unless it's what's being asked for. The source window shows a tutorial's words,
    which must never pass for the app's own text."""
    return title.startswith(OWN_TITLE) and OWN_TITLE.casefold() not in wanted.casefold()


def pick(wins: list[Win], label: str) -> Optional[Win]:
    """The window a step's label means: an app kind ("Browser") → its front window, else the front window whose
    title contains the label. `wins` is in z-order (front first); our overlay and minimised windows never count,
    and neither does a browser tab that happens to mention the app."""
    names = APP_KINDS.get(label.strip().casefold(), (label,))
    for w in wins:
        if w.minimized or w.title == OVERLAY_TITLE or w.area <= 0 or foreign_browser(w.title, label) or ours(w.title, label):
            continue
        if any(n.casefold() in w.title.casefold() for n in names):
            return w
    return None


def document_open(title: str) -> bool:
    """SOLIDWORKS names the open document in brackets: "SOLIDWORKS … - [Part1 *]"."""
    return bool(re.search(r"\[[^\]]+\]\s*$", title))


def folder_from_title(title: str) -> Optional[str]:
    """VS Code titles read "file - folder - Visual Studio Code" (or "folder - Visual Studio Code")."""
    parts = [p.strip() for p in title.split(" - ")]
    if len(parts) < 2 or "visual studio code" not in parts[-1].casefold():
        return None
    return parts[-2] or None


def folder_from_workspace_json(text: str) -> Optional[Path]:
    """VS Code's workspaceStorage/<id>/workspace.json: {"folder": "file:///c%3A/Users/…/youtube-clone"}."""
    try:
        uri = json.loads(text).get("folder") or ""
    except ValueError:
        return None
    u = urlparse(uri)
    if u.scheme != "file":
        return None
    p = unquote(u.path)
    if re.match(r"^/[a-zA-Z]:", p):            # /c:/Users → c:/Users
        p = p[1:]
    return Path(p)


def vscode_folder(title_part: str, storage: Optional[Path] = None) -> Optional[Path]:
    """The folder open in the VS Code window whose title contains `title_part`, so `file` checks know where
    to look. VS Code records each opened folder in workspaceStorage; the most recently used one with the
    window's folder name wins."""
    name = folder_from_title(title_part) or title_part
    storage = storage or Path.home() / "AppData" / "Roaming" / "Code" / "User" / "workspaceStorage"
    if not storage.is_dir():
        return None
    best: tuple[float, Optional[Path]] = (0.0, None)
    for ws in storage.glob("*/workspace.json"):
        try:
            p = folder_from_workspace_json(ws.read_text(encoding="utf-8"))
            mtime = ws.parent.stat().st_mtime
        except OSError:
            continue
        if p is not None and p.name.casefold() == name.casefold() and p.is_dir() and mtime > best[0]:
            best = (mtime, p)
    return best[1]


# ---------- Windows -------------------------------------------------------------------------------
def _user32():
    import ctypes
    return ctypes.windll.user32


def top_windows() -> list[Win]:
    """Visible top-level windows with a title, front first."""
    if sys.platform != "win32":
        return []
    import ctypes
    import ctypes.wintypes as wt

    u32 = _user32()
    dwm = ctypes.windll.dwmapi
    out: list[Win] = []
    proto = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def cb(hwnd, _):
        if not u32.IsWindowVisible(hwnd):
            return True
        n = u32.GetWindowTextLengthW(hwnd)
        if n == 0:
            return True
        buf = ctypes.create_unicode_buffer(n + 1)
        u32.GetWindowTextW(hwnd, buf, n + 1)
        cloaked = ctypes.c_int(0)          # UWP windows on other virtual desktops are "visible" but cloaked
        dwm.DwmGetWindowAttribute(hwnd, 14, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
        if cloaked.value:
            return True
        out.append(Win(hwnd=int(hwnd), title=buf.value, rect=frame(int(hwnd)), minimized=bool(u32.IsIconic(hwnd))))
        return True

    u32.EnumWindows(proto(cb), 0)
    return out


def frame(hwnd: int) -> tuple[int, int, int, int]:
    """The visible frame (DWM extended frame bounds: no invisible resize border), x y w h."""
    import ctypes
    import ctypes.wintypes as wt

    r = wt.RECT()
    if ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
        _user32().GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def same_process(hwnd: int) -> list[Win]:
    """The other visible top-level windows of hwnd's process, back to front: its dialogs, flyouts and menus."""
    if sys.platform != "win32":
        return []
    import ctypes
    import ctypes.wintypes as wt

    u32 = _user32()
    pid = wt.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    out: list[Win] = []
    proto = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def cb(h, _):
        if int(h) == hwnd or not u32.IsWindowVisible(h) or u32.IsIconic(h):
            return True
        p = wt.DWORD()
        u32.GetWindowThreadProcessId(h, ctypes.byref(p))
        if p.value == pid.value:
            r = frame(int(h))
            if r[2] > 4 and r[3] > 4:
                out.append(Win(hwnd=int(h), title="", rect=r))
        return True

    u32.EnumWindows(proto(cb), 0)
    out.reverse()
    return out


def display_scale(hwnd: int) -> float:
    """Windows' display scale for the window: 1.5 at 150 %."""
    try:
        return (_user32().GetDpiForWindow(hwnd) or 96) / 96
    except Exception:
        return 1.0


def foreground() -> Optional[Win]:
    if sys.platform != "win32":
        return None
    import ctypes

    u32 = _user32()
    h = u32.GetForegroundWindow()
    if not h:
        return None
    n = u32.GetWindowTextLengthW(h)
    buf = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(h, buf, n + 1)
    return Win(hwnd=int(h), title=buf.value, rect=frame(int(h)), minimized=bool(u32.IsIconic(h)))


def find(label: str) -> Optional[Win]:
    return pick(top_windows(), label)
