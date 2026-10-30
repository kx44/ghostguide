"""Find VS Code targets with Windows UI Automation, no model (phase 2 stand-in for the phase 3 resolver).

Phase 1 found that looking targets up by label alone fails in VS Code (0 of 11): the editor is named after
the file, New File only exists while the folder header is hovered, and so on. So each target kind gets its
own rule, worked out from what UIA does expose:

- editor tabs        TabItem named after the file
- New File           the "New File..." button once the header is hovered; before that, where it will appear
                     (first of the four action icons at the right end of the folder header)
- filename box       the Edit inside the Explorer tree while a new file is being named
- Editor             one line of the editor. The caret line comes from the status bar ("Ln 18, Col 39") and
                     its top from Monaco's screen-reader textarea, which sits on the caret line; other lines
                     are pitch × distance away, pitch measured from the line numbers in the gutter. Which line
                     comes from the step's `where` ("inside <body>", "before <title>", "end", …) read against
                     the editor text.
- menu_path          the menu item once its menu is open, else the first chip's target ("index.html (right-click)")
- anything else      an on-screen control whose name is the label

Needs `editor.accessibilitySupport: on` in the workspace, or Monaco hides its text and caret from UIA.
The matching functions are pure (they work on dumped element dicts), so they are unit-tested off Windows.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Iterable, Optional

from engine.schema.messages import Box, Line
from engine.schema.tutorial import Step

# VS Code appends key hints to UIA names: "Toggle Panel (Ctrl+J)", "Split Editor Right (Ctrl+\) [Alt] …".
_HINTS = re.compile(r"\s*(\[alt\].*|\((ctrl|alt|shift|win|f\d+)[^)]*\))\s*$", re.I)
_LN = re.compile(r"^Ln (\d+), Col (\d+)")
ICON_RATIO = 0.725       # header action button / header height (37 / 51 at 180 %, measured hovered)
ICON_PAD_RATIO = 0.51    # gap right of the last action button / header height (26 / 51)
NEW_FILE_ICONS = 4       # New File, New Folder, Refresh, Collapse; New File is the leftmost
MINIMAP_PX = 120         # keep the line box clear of the minimap
MIN_LINE_PX = 10         # a textarea shorter than this is parked (editor not focused), not on the caret line
TAB_TO_LINE = 0.62       # editor line height / editor tab height (34.2 / 56 at 180 %)
GUTTER_LINES = 3.5       # gutter width in line heights (122 / 34.2), for an unfocused editor


def norm(s: Optional[str]) -> str:
    s = " ".join((s or "").replace("…", "...").split()).casefold()
    prev = None
    while prev != s:
        prev, s = s, _HINTS.sub("", s)
    return s


def _box(rect) -> Box:
    x, y, w, h = rect
    return Box(x=int(x), y=int(y), w=int(w), h=int(h))


def _visible(el: dict) -> bool:
    r = el.get("rect")
    return bool(r) and r[2] > 0 and r[3] > 0 and not el.get("offscreen", False)


def _inside(r, outer, slack: int = 2) -> bool:
    return (r[0] >= outer[0] - slack and r[1] >= outer[1] - slack
            and r[0] + r[2] <= outer[0] + outer[2] + slack and r[1] + r[3] <= outer[1] + outer[3] + slack)


def _named(els: Iterable[dict], types: set, name: str) -> list[dict]:
    n = norm(name)
    return [e for e in els if e.get("type") in types and _visible(e) and norm(e.get("name")) == n]


# ---------- editor state ------------------------------------------------------------------------
@dataclass
class Editor:
    file: str                 # active file, e.g. index.html
    text: str                 # whole document (accessibilityPageSize must cover it)
    caret_line: int           # 1-based
    caret_top: int            # px, top of the caret line
    line_h: float             # px per line
    left: int                 # px, where code starts (right of the gutter)
    right: int
    top: int                  # editor viewport
    bottom: int
    focused: bool = True      # False: caret position unknown, lines placed from the top (see editor_from)
    scroll_known: bool = True

    @property
    def lines(self) -> list[str]:
        return self.text.split("\n")

    def line_box(self, n: int) -> Box:
        """Box around line n, clamped into the viewport (so a line scrolled away points at the edge it's past)."""
        y = self.caret_top + (n - self.caret_line) * self.line_h
        y = min(max(y, self.top), self.bottom - self.line_h)
        return Box(x=self.left - 6, y=int(round(y)) - 2, w=max(40, self.right - self.left + 6), h=int(round(self.line_h)) + 4)


def editor_from(els: list[dict]) -> Optional[Editor]:
    """The active editor from a dump: the selected editor tab names the file, the Edit with that name is
    Monaco's textarea (on the caret line), the status bar gives the caret line, the Group with the file's
    name is the editor body."""
    tabs = [e for e in els if e.get("type") == "TabItem" and e.get("selected") and _visible(e)
            and "." in (e.get("name") or "")]
    edits = [e for e in els if e.get("type") == "Edit" and e.get("value") is not None and e.get("rect")]
    ed = None
    for t in tabs:
        ed = next((e for e in edits if norm(e.get("name")) == norm(t["name"])), None)
        if ed:
            break
    if ed is None:   # no tab marked selected: any Edit named like a file
        ed = next((e for e in edits if re.search(r"\.\w+$", e.get("name") or "")), None)
    ln = next((e for e in els if e.get("type") == "Button" and _LN.match(e.get("name") or "")), None)
    if ed is None or ln is None:
        return None
    caret = int(_LN.match(ln["name"]).group(1))
    x, y, w, h = ed["rect"]
    bodies = [e["rect"] for e in els if e.get("type") == "Group" and e.get("name") == ed["name"]
              and e.get("rect") and e["rect"][2] > 0]
    body = next((b for b in bodies if x >= b[0] - 2 and y >= b[1] - max(h, 2)), bodies[0] if bodies else None)
    if h >= MIN_LINE_PX and w > 0:            # focused: the textarea sits on the caret line
        if body is None:
            body = [x, y - 20 * h, w, 40 * h]
        right = min(x + w, body[0] + body[2] - MINIMAP_PX)
        return Editor(file=ed["name"], text=ed["value"], caret_line=caret, caret_top=y, line_h=float(h),
                      left=x, right=right, top=body[1], bottom=body[1] + body[3])
    # Not focused: Monaco parks the textarea at the editor's top-left, so the caret can't be placed. When the
    # whole file fits there is no scroll, so line 1 is at the top; line height ≈ 0.62 × the editor tab height.
    if body is None:
        return None
    tab = next((e["rect"] for e in tabs if norm(e.get("name")) == norm(ed["name"])), None)
    lh = (tab[3] * TAB_TO_LINE) if tab else 34.0
    fits = (ed["value"].count("\n") + 2) * lh <= body[3]
    left = body[0] + int(round(lh * GUTTER_LINES))
    return Editor(file=ed["name"], text=ed["value"], caret_line=1, caret_top=body[1], line_h=lh, left=left,
                  right=body[0] + body[2] - MINIMAP_PX, top=body[1], bottom=body[1] + body[3],
                  focused=False, scroll_known=fits)


# ---------- which line a `where` means ----------------------------------------------------------
_TOKEN = re.compile(r"</?[a-zA-Z][^>]*>|\.[a-zA-Z][\w-]+")


def _tokens(s: str) -> list[str]:
    out = []
    for t in _TOKEN.findall(s):
        out.append(t[1:] if t.startswith(".") else t)
    return out


def _find(lines: list[str], needle: str, start: int = 0) -> Optional[int]:
    """0-based index of the first line at or after `start` containing needle (spaces ignored)."""
    n = re.sub(r"\s+", "", needle)
    if n.startswith("<") and not n.startswith("</") and n.endswith(">") and len(n) > 3:
        n = n[:-1]            # "<body>" also matches "<body class=…>"
    for i in range(max(0, start), len(lines)):
        if n in re.sub(r"\s+", "", lines[i]):
            return i
    return None


def _last_code_line(lines: list[str]) -> int:
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip():
            return i
    return 0


def target_line(text: str, where: Optional[str], caret_line: Optional[int] = None) -> Optional[int]:
    """1-based editor line the step's `where` points at, or the caret line when it can't be read.
    `where` looks like "index.html, inside <body>"; the part naming the file is dropped."""
    lines = text.split("\n")
    w = (where or "").strip()
    w = re.sub(r"^[\w.-]+\.\w+\s*,\s*", "", w)                     # "index.html, …"
    lw = w.casefold()
    m = re.search(r"\bline (\d+)", lw)
    if m:
        return int(m.group(1))
    if re.fullmatch(r"(at the )?(top|start)", lw):
        return 1
    if re.fullmatch(r"(at the )?(end|bottom)", lw):
        last = _last_code_line(lines)
        return last + 2 if last + 1 < len(lines) or lines[last].strip() else last + 1
    # "inside X, before Y" / "inside X after Y" / "before Y" / "after the thumbnail </a>" / "in X after class attribute"
    start = 0
    m = re.match(r"(inside|in)\s+(.+?)(?:,?\s+(before|after)\s+(.+))?$", w, re.I)
    if m:
        scope = _tokens(m.group(2)) or [m.group(2).strip()]
        i = _find(lines, scope[0])
        if i is None:
            return caret_line
        rel, rest = (m.group(3) or "").casefold(), m.group(4) or ""
        if not rel:
            return i + 2                                            # first line inside the opening tag
        if re.search(r"attribute", rest, re.I):
            return i + 1                                            # same line, inside the tag
        start, w, lw = i, f"{rel} {rest}", f"{rel} {rest}".casefold()
    m = re.match(r"(before|after)\s+(?:the\s+)?(.+)$", w, re.I)
    if not m:
        return caret_line
    rel, rest = m.group(1).casefold(), m.group(2)
    toks = _tokens(rest)
    words = [x for x in re.sub(_TOKEN, " ", rest).split() if len(x) > 2 and x.casefold() not in ("the", "link")]
    if "link" in rest.casefold() and not toks:
        toks = ["</a>"]
    i = start
    for wd in words:                                                # context words narrow the search first
        j = _find(lines, wd, i)
        if j is not None:
            i = j
    if toks:
        j = _find(lines, toks[0], i)
        if j is None:
            return caret_line
        i = j
    elif not words:
        return caret_line
    return i + 1 if rel == "before" else i + 2


# ---------- per-target rules --------------------------------------------------------------------
def new_file_box(els: list[dict]) -> tuple[Optional[Box], bool]:
    """(box, exact). Exact once hovering shows the real button; else where the icon will appear."""
    btn = [e for e in els if e.get("type") == "Button" and _visible(e) and norm(e.get("name")).startswith("new file")]
    if btn:
        return _box(btn[0]["rect"]), True
    hdr = [e for e in els if e.get("type") == "Button" and _visible(e)
           and norm(e.get("name")).startswith("explorer section:")]
    if not hdr:
        return None, False
    x, y, w, h = hdr[0]["rect"]
    icon = int(round(h * ICON_RATIO))
    # Same box the hovered button will have, so hovering doesn't move the outline (or the card next to it).
    return Box(x=x + w - NEW_FILE_ICONS * icon - int(round(h * ICON_PAD_RATIO)), y=y + (h - icon) // 2,
               w=icon, h=icon), False


def filename_box(els: list[dict]) -> Optional[Box]:
    tree = next((e for e in els if e.get("type") == "Tree" and _visible(e)
                 and "explorer" in norm(e.get("name"))), None)
    if tree is None:
        return None
    for e in els:
        if e.get("type") == "Edit" and _visible(e) and _inside(e["rect"], tree["rect"], slack=60):
            return _box(e["rect"])
    return None


def editor_tab(els: list[dict], label: str) -> Optional[Box]:
    hits = _named(els, {"TabItem"}, label)
    return _box(min(hits, key=lambda e: e["rect"][1])["rect"]) if hits else None


def named_control(els: list[dict], label: str) -> Optional[Box]:
    for types in ({"Button", "MenuItem", "TabItem", "TreeItem", "ListItem", "CheckBox", "Hyperlink", "SplitButton"},
                  {"Edit", "ComboBox", "Text", "Group"}):
        hits = _named(els, types, label)
        if hits:
            return _box(hits[0]["rect"])
    return None


def locate_in(step: Step, els: list[dict], editor: Optional[Editor]) -> tuple[Optional[Box], Optional[Line], str]:
    """(box, line, how) for one step over a dump. `how` says which rule hit, for logs and the landing check."""
    t = step.target
    label = norm(t.label)
    if step.action == "menu_path" and t.menu_path:
        last = t.menu_path[-1]
        b = named_control(els, last)
        if b:
            return b, None, f"menu item '{last}'"
        first = re.sub(r"\s*\(.*?\)\s*$", "", t.menu_path[0])
        b = named_control(els, first)
        return (b, None, f"first chip '{first}'") if b else (None, None, "menu path not on screen")
    if label.startswith("new file"):
        b, exact = new_file_box(els)
        return b, None, "New File button" if exact else "New File (estimated: hover the folder header)"
    if t.kind == "field" and "filename" in label:
        b = filename_box(els)
        return b, None, "filename box" if b else "filename box not open"
    if t.kind == "field" and label == "editor":
        if editor is None:
            return None, None, "no editor (is editor.accessibilitySupport on?)"
        want = (t.where or "").split(",")[0].strip()
        if re.search(r"\.\w+$", want) and norm(want) != norm(editor.file):
            return None, None, f"{want} is not the active editor ({editor.file})"
        n = target_line(editor.text, t.where, editor.caret_line if editor.focused else None)
        if n is None or not editor.scroll_known:
            return None, None, "click into the editor so its caret and scroll can be read"
        return editor.line_box(n), None, f"editor line {n}" + ("" if editor.focused else " (editor not focused)")
    if t.kind == "tab":
        b = editor_tab(els, t.label)
        return b, None, "editor tab" if b else "tab not open"
    b = named_control(els, t.label)
    return b, None, "named control" if b else "not found"


def insert_col(text: str, where: Optional[str], n: int) -> Optional[int]:
    """Column (0-based, tabs as 4) where a step types into the middle of line n rather than on a line of its
    own: "… after class attribute" means just before the tag's closing `>`. None for whole-line inserts."""
    if not where or "attribute" not in where.casefold():
        return None
    lines = text.split("\n")
    if not 1 <= n <= len(lines):
        return None
    line = lines[n - 1].expandtabs(4)
    i = line.rfind(">")
    if i > 0 and line[i - 1] == "/":
        i -= 1                                          # self-closing: before "/>"
    return i if i >= 0 else None


def editor_extra(ed: Optional[Editor], bg: Optional[str], col: Optional[int] = None) -> dict:
    """What the overlay needs to draw ghost code inside the editor: its visible area (code column to the
    minimap, physical px) to clip to, its background colour for a solid backing over the code already
    there, the line height so multi-line code lines up with the editor's lines, and for a mid-line insert
    the column to start at."""
    if ed is None:
        return {}
    out = {"clip": {"x": ed.left - 6, "y": ed.top, "w": ed.right - ed.left + 6, "h": ed.bottom - ed.top},
           "line_h": round(ed.line_h, 2)}
    if bg:
        out["backing"] = bg
    if col is not None:
        out["col"] = col
    return out


# ---------- gutter pitch (pure) -----------------------------------------------------------------
def pitch_from_rows(ink: list[float], approx: float) -> Optional[float]:
    """Line pitch from a per-row ink profile of the line-number gutter: the autocorrelation peaks at every
    multiple of the pitch. Find the peak near one line, then follow it out to k lines (k·pitch is measured
    to the same ±½ px, so the pitch gets k times finer). None when fewer than 3 lines show."""
    n = len(ink)
    if n < approx * 3 or approx <= 2:
        return None
    mean = sum(ink) / n
    x = [v - mean for v in ink]
    if not any(x):
        return None

    def ac(lag: int) -> float:
        return sum(x[i] * x[i + lag] for i in range(n - lag)) / (n - lag)

    def peak(centre: float, half: float) -> Optional[float]:
        lo, hi = max(2, int(centre - half)), min(n - 2, int(centre + half) + 1)
        if hi - lo < 3:
            return None
        vals = {lag: ac(lag) for lag in range(lo - 1, hi + 2)}
        lag = max(range(lo, hi + 1), key=vals.get)
        if vals[lag] <= 0:
            return None
        a, b, c = vals[lag - 1], vals[lag], vals[lag + 1]
        d = a - 2 * b + c
        # parabola through the top 3; a flat top makes d tiny and the shift huge, so keep it within ±½ px
        return lag + (max(-0.5, min(0.5, 0.5 * (a - c) / d)) if d < 0 else 0.0)

    p = peak(approx, approx * 0.2)
    if p is None:
        return None
    k = 2
    while (k + 0.5) * p < n * 0.6:
        q = peak(k * p, p * 0.25)
        if q is None:
            break
        p = q / k
        k += 1
    return p if k >= 3 and 0.75 * approx <= p <= 1.25 * approx else None


# ---------- Windows layer -----------------------------------------------------------------------
def dump(window: str, max_depth: int = 60, max_elements: int = 6000, tries: int = 3) -> list[dict]:
    """Every UIA element of the first top-level window whose title contains `window`. The walk itself can
    throw when the UI changes under it (a menu closing, VS Code still starting), so it retries."""
    for i in range(tries):
        try:
            return _dump(window, max_depth, max_elements)
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(0.2)
    return []


def _dump(window: str, max_depth: int, max_elements: int) -> list[dict]:
    import uiautomation as auto

    out: list[dict] = []
    for top in auto.GetRootControl().GetChildren():
        title = top.Name or ""
        if window.casefold() not in title.casefold():
            continue
        for ctrl, _ in auto.WalkControl(top, includeTop=True, maxDepth=max_depth):
            if len(out) >= max_elements:
                break
            try:
                r = ctrl.BoundingRectangle
                t = ctrl.ControlTypeName.removesuffix("Control")
                el = {"name": ctrl.Name, "type": t, "rect": [r.left, r.top, r.width(), r.height()],
                      "offscreen": bool(ctrl.IsOffscreen)}
                if t == "Edit":
                    vp = ctrl.GetPattern(auto.PatternId.ValuePattern)
                    if vp:
                        el["value"] = vp.Value
                elif t == "TabItem":
                    sp = ctrl.GetPattern(auto.PatternId.SelectionItemPattern)
                    if sp:
                        el["selected"] = bool(sp.IsSelected)
            except Exception:   # elements vanish mid-walk; keep going
                continue
            out.append(el)
        break
    return out


class VSCodeLocator:
    """Live locator: dumps the VS Code window and applies the rules. `window` is part of its title,
    e.g. "youtube-clone - Visual Studio Code" when several VS Code windows are open."""

    def __init__(self, window: str = "Visual Studio Code"):
        self.window = window
        self._gutter: dict[tuple, tuple[Optional[float], Optional[str]]] = {}   # geometry → (pitch, bg colour)
        self.last_how = ""
        self.last_seconds = 0.0
        self.last_extra: dict = {}         # for editor lines: what ghost text needs to sit in the editor

    def locate(self, step: Step) -> tuple[Optional[Box], Optional[Line]]:
        t0 = time.perf_counter()
        els = dump(self.window)
        ed = editor_from(els)
        bg = None
        if ed is not None:
            pitch, bg = self._gutter_info(ed)
            ed.line_h = pitch or ed.line_h
        box, line, self.last_how = locate_in(step, els, ed)
        self.last_extra = {}
        if box is not None and ed is not None and self.last_how.startswith("editor line"):
            n = int(self.last_how.split()[2])
            self.last_extra = editor_extra(ed, bg, insert_col(ed.text, step.target.where, n))
        self.last_seconds = time.perf_counter() - t0
        return box, line

    def _gutter_info(self, ed: Editor) -> tuple[Optional[float], Optional[str]]:
        key = (ed.left, ed.top, ed.bottom, int(ed.line_h))
        if key not in self._gutter:
            try:
                self._gutter[key] = self._measure(ed)
            except Exception:
                self._gutter[key] = (None, None)
        return self._gutter[key]

    @staticmethod
    def _measure(ed: Editor) -> tuple[Optional[float], Optional[str]]:
        """Line pitch and the editor's background colour, both from one grab of the line-number gutter
        (the gutter has the editor's background in the usual themes; the median pixel is background)."""
        from PIL import ImageGrab

        gutter_w = max(30, int(ed.line_h * 2.2))
        x1 = ed.left - 8
        rgb = ImageGrab.grab(bbox=(x1 - gutter_w, ed.top, x1, ed.bottom), all_screens=True).convert("RGB")
        img = rgb.convert("L")
        w, h = img.size
        px, cpx = img.load(), rgb.load()
        samples = sorted(((px[i, j], cpx[i, j]) for i in range(0, w, 3) for j in range(0, h, 3)))
        bg, colour = samples[len(samples) // 2]
        ink = [sum(abs(px[i, j] - bg) for i in range(w)) / w for j in range(h)]
        return pitch_from_rows(ink, ed.line_h), "#%02x%02x%02x" % colour
