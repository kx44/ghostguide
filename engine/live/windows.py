"""Which windows are on screen (live step 3): top-level windows in z-order, the front one, and the app window
a step means ("Browser" → the front Chrome / Edge / Firefox window). Plain Win32 through ctypes, no UIA, so
it's instant (a UIA walk of one window takes ~0.7 s).

A tutorial's name for an app needn't be in the window's title: its program counts too, and when neither says, you
point at the window once (`use_front`) and that program is the app from then on.

Positions are physical pixels (the engine is per-monitor DPI aware). The pure helpers at the top are
unit-tested off Windows; everything that calls Win32 is below `# ---------- Windows`.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import unquote, urlparse

# Window-kind target labels that name a kind of app rather than a title.
APP_KINDS = {
    "browser": ("Google Chrome", "Microsoft Edge", "Mozilla Firefox", "Brave", "Opera"),
    "terminal": ("Windows PowerShell", "Command Prompt", "Terminal"),
    "file explorer": ("File Explorer",),
}
# A title says little for these: a terminal's is whatever ran last. So their programs are looked for first.
KIND_PROGRAMS = {
    "browser": ("chrome", "msedge", "firefox", "brave", "opera"),
    "terminal": ("windowsterminal", "powershell", "pwsh", "cmd", "conhost"),
}
KIND_ALIASES = {"windows terminal": "terminal", "powershell": "terminal", "windows powershell": "terminal",
                "command prompt": "terminal", "cmd": "terminal", "web browser": "browser"}
NOT_THE_NAME = {"microsoft", "ms", "adobe", "autodesk", "windows", "the", "app", "application", "desktop", "program", "software"}
OVERLAY_TITLE = "GhostGuide overlay"
OWN_TITLE = "GhostGuide"
BINDINGS_FILE = "windows.json"


@dataclass
class Win:
    hwnd: int
    title: str
    rect: tuple[int, int, int, int]      # x, y, w, h (visible frame, physical px)
    minimized: bool = False

    @property
    def area(self) -> int:
        return self.rect[2] * self.rect[3]


@dataclass(frozen=True)
class Program:
    exe: str = ""                        # file name without .exe, lower case
    description: str = ""                # what the file calls itself: "Microsoft Word" for WINWORD.EXE


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


def program_is(label: str, p: Program) -> bool:
    """The program a tutorial's name for an app means. "Microsoft Word" is WINWORD.EXE, which calls itself that, though its
    window says "Document1 - Word". Every word of the name that says which app must be there."""
    words = [w for w in re.findall(r"[\w+#]+", label.casefold()) if w not in NOT_THE_NAME]
    said = set(re.findall(r"[\w+#]+", p.description.casefold()))
    return bool(words) and all(w in said or (len(w) >= 3 and w in p.exe) for w in words)


def pick(wins: list[Win], label: str, program_of: Optional[Callable[[Win], Program]] = None,
         bound: Optional[str] = None) -> Optional[Win]:
    """The window a step's label means, whatever its title says. In order: the program you chose for this name (`bound`),
    a kind of app's programs ("Terminal"), a title containing the name, a program that goes by the name. `wins` is in
    z-order (front first); our overlay and minimised windows never count, and neither does a browser tab that happens
    to mention the app."""
    low = label.strip().casefold()
    kind = KIND_ALIASES.get(low, low)
    usable = [w for w in wins if not (w.minimized or w.title == OVERLAY_TITLE or w.area <= 0 or ours(w.title, label))]
    program = program_of or (lambda w: Program())
    if bound:
        found = next((w for w in usable if program(w).exe == bound), None)
        if found:
            return found
    if kind in KIND_PROGRAMS:
        found = next((w for w in usable if program(w).exe in KIND_PROGRAMS[kind]), None)
        if found:
            return found
    names = APP_KINDS.get(kind, (label,))
    titled = [w for w in usable if not foreign_browser(w.title, label)]
    found = next((w for w in titled if any(n.casefold() in w.title.casefold() for n in names)), None)
    if found or program_of is None:
        return found
    return next((w for w in titled if program_is(label, program(w))), None)


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


_programs: dict[int, Program] = {}        # by process id: looked up every tick while an app isn't found


def program(hwnd: int) -> Program:
    """The program behind a window."""
    if sys.platform != "win32":
        return Program()
    import ctypes
    import ctypes.wintypes as wt

    pid = wt.DWORD()
    _user32().GetWindowThreadProcessId(wt.HWND(hwnd), ctypes.byref(pid))
    if pid.value in _programs:
        return _programs[pid.value]
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wt.HANDLE
    k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
    k32.CloseHandle.argtypes = [wt.HANDLE]
    k32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
    handle = k32.OpenProcess(0x1000, False, pid.value)      # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return Program()                                    # a process running as admin: not remembered, it may be asked again
    try:
        size = wt.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if not k32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return Program()
    finally:
        k32.CloseHandle(handle)
    _programs[pid.value] = Program(Path(buf.value).stem.casefold(), _file_description(buf.value))
    return _programs[pid.value]


def _file_description(path: str) -> str:
    """What an .exe calls itself, from its version resource. Nothing is run."""
    import ctypes
    import ctypes.wintypes as wt

    ver = ctypes.WinDLL("version")
    ver.GetFileVersionInfoSizeW.argtypes = [wt.LPCWSTR, ctypes.POINTER(wt.DWORD)]
    ver.GetFileVersionInfoW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p]
    ver.VerQueryValueW.argtypes = [ctypes.c_void_p, wt.LPCWSTR, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wt.UINT)]
    size = ver.GetFileVersionInfoSizeW(path, None)
    if not size:
        return ""
    data = ctypes.create_string_buffer(size)
    if not ver.GetFileVersionInfoW(path, 0, size, data):
        return ""
    value, length = ctypes.c_void_p(), wt.UINT()
    if not ver.VerQueryValueW(data, r"\VarFileInfo\Translation", ctypes.byref(value), ctypes.byref(length)) or length.value < 4:
        return ""
    lang, page = ctypes.cast(value, ctypes.POINTER(wt.WORD))[0:2]
    if not ver.VerQueryValueW(data, rf"\StringFileInfo\{lang:04x}{page:04x}\FileDescription", ctypes.byref(value), ctypes.byref(length)):
        return ""
    return ctypes.wstring_at(value, length.value).split("\0")[0].strip()


_chosen: dict[str, dict[str, str]] = {}   # by file: find() runs many times a second


def _bindings_path() -> Path:
    from engine.appmap.store import local_dir
    return local_dir() / BINDINGS_FILE


def _bindings() -> dict[str, str]:
    path = str(_bindings_path())
    if path not in _chosen:
        try:
            got = json.loads(Path(path).read_text(encoding="utf-8"))
            _chosen[path] = {str(k): str(v) for k, v in got.items()} if isinstance(got, dict) else {}
        except (OSError, ValueError):
            _chosen[path] = {}
    return _chosen[path]


def bound_to(label: str) -> Optional[str]:
    """The program you chose for this name, if you have."""
    return _bindings().get(label.strip().casefold())


def use_front(label: str) -> Optional[str]:
    """You say the window in front is what this name means. Remembers its program, so it's asked once for each app and the
    window's title can change freely. → what it's called, or None when there's nothing fit to choose: never our own."""
    w = foreground()
    if w is None or not w.title or w.title == OVERLAY_TITLE or w.title.startswith(OWN_TITLE):
        return None
    p = program(w.hwnd)
    if not p.exe:
        return None
    chosen = _bindings()
    chosen[label.strip().casefold()] = p.exe
    path = _bindings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(chosen, indent=1, ensure_ascii=False), encoding="utf-8")
    return p.description or p.exe


def find(label: str) -> Optional[Win]:
    return pick(top_windows(), label, lambda w: program(w.hwnd), bound_to(label))
