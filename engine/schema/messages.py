"""Engine ⇄ overlay messages over the local WebSocket.

Mirrored in TypeScript in `overlay/shared/messages.ts`; `tests/test_messages.py` checks both list the
same message types and styles. Every coordinate is in physical screen pixels (virtual desktop, the same
space as UIA and screenshots); the overlay converts to its own DIPs per display.
"""
from __future__ import annotations

import json
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

# The 12 guidance styles, plus `card` for `look` steps (tooltip card alone, with Next).
Style = Literal[
    "outline",        # 1  button, first time: outline + tooltip
    "ghost_line",     # 2  cursor action, first time: animated ghost line + tooltip
    "beacon",         # 3  button, repeat
    "static_line",    # 4  cursor action, repeat
    "code_card",      # 5  type a value: outline where it goes + the text in the card, with Copy
    "ghost_text",     # 5 (KIV) the value as faint text in place; messy over existing code, so unused
    "keycaps",        # 6  keyboard shortcut
    "mask",           # 7  pick in the model
    "path_chips",     # 8  hidden: menu path
    "offscreen",      # 9  hidden: off-screen edge pill
    "taskbar",        # 10 switch app
    "click_type",     # 11 mouse icon (added on top of outline / path_chips via extra.click_type)
    "signal_card",    # 12 wait
    "card",           # look: card only
]
STYLES: tuple[str, ...] = Style.__args__  # type: ignore[attr-defined]
Scheme = Literal["light", "dark"]
StepStatus = Literal["pending", "done", "skipped"]


class _Msg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    def to_wire(self) -> dict:
        return self.model_dump(mode="json", exclude_none=True)


class Box(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: int
    y: int
    w: int
    h: int

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2


class Line(BaseModel):
    start: tuple[int, int] = Field(alias="from")
    end: tuple[int, int] = Field(alias="to")
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    def to_wire(self) -> dict:
        return {"from": list(self.start), "to": list(self.end)}


class Display(BaseModel):
    """One monitor as the overlay reports it, in physical pixels."""
    model_config = ConfigDict(extra="forbid")
    id: Union[int, str]
    x: int
    y: int
    w: int
    h: int
    scale: float = 1.0
    primary: bool = False


class StepInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n: int
    of: int
    title: str
    part: Optional[str] = None
    source_t: Optional[str] = None
    confidence: Optional[str] = None


class Card(BaseModel):
    model_config = ConfigDict(extra="forbid")
    meta: str                         # "Step 2 of 23 · YouTube clone"
    title: str
    why: Optional[str] = None
    detail: Optional[str] = None      # what to do, e.g. "Type index.html, then press Enter."
    done_when: Optional[str] = None   # the step's `check`, in plain words
    suggested: Optional[str] = None   # our value when the author left it open; labelled as ours
    actions: list[str] = Field(default_factory=list)   # show_me | do_it | next | skip_wait | use_window
    low_confidence: bool = False
    dev_hint: Optional[str] = None    # dev pins: "not pinned yet, Ctrl+Alt+P…"
    compact: bool = False             # repeat steps: title + Next only, so the instruction never vanishes
    up_next: Optional[str] = None     # the next step's title, shown on compact cards
    source: Optional[str] = None      # the source button's words: "▶ 01:40" for a clip, "Source" for text
    confirm: bool = False             # Do it for me is waiting for its second press


# ---------------- engine → overlay ----------------

class Guide(_Msg):
    type: Literal["guide"] = "guide"
    step: StepInfo
    style: Style
    scheme: Scheme
    box: Optional[Box] = None          # target in physical px; None = no on-screen target
    line: Optional[Line] = None        # ghost line path, for draw_line / drag
    extra: dict[str, Any] = Field(default_factory=dict)
    card: Optional[Card] = None        # None = no card (beacon, static line)

    def to_wire(self) -> dict:
        d = super().to_wire()
        if self.line is not None:
            d["line"] = self.line.to_wire()
        return d


class Clear(_Msg):
    type: Literal["clear"] = "clear"
    reason: Optional[str] = None       # hidden | finished | capture


class State(_Msg):
    """Everything the step rail and control bar show."""
    type: Literal["state"] = "state"
    tutorial: str
    current: int                       # 1-based; of+1 when finished
    of: int
    hidden: bool
    finished: bool
    titles: list[str]
    statuses: list[StepStatus]
    scheme: Scheme
    local_only: bool = False           # the switch: nothing from the screen leaves this PC
    privacy: Optional[str] = None      # the tray's statement of what's happening right now


class Toast(_Msg):
    type: Literal["toast"] = "toast"
    text: str
    kind: Literal["ok", "warn"] = "ok"
    ms: int = 2000


class ShowMe(_Msg):
    """Play the ghost cursor (never clicks)."""
    type: Literal["show_me"] = "show_me"
    to: tuple[int, int]
    path: Optional[list[tuple[int, int]]] = None   # for lines: press at path[0], move along, release at end
    click: Literal["left", "right", "double", "none"] = "left"


class Mark(_Msg):
    """Outline turns ok / warn (from the step checks; Next flashes ok)."""
    type: Literal["mark"] = "mark"
    result: Literal["ok", "bad"]


class StartItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    ok: Optional[bool] = None          # None = yours to look at; the engine can't read it
    use_window: bool = False           # it can't tell which window is the app: offers Use this window


class StartCheck(_Msg):     # shell/startCheck.ts
    type: Literal["start_check"] = "start_check"
    tutorial: str
    items: list[StartItem]


class CompileProgress(_Msg):     # shell/importScreen.ts
    type: Literal["compile_progress"] = "compile_progress"
    stage: str
    pct: float


class CompileDone(_Msg):         # shell/importScreen.ts
    type: Literal["compile_done"] = "compile_done"
    ok: bool
    path: Optional[str] = None
    title: Optional[str] = None
    steps: Optional[int] = None
    cached: bool = False
    cost_usd: Optional[float] = None
    score: Optional[list[str]] = None   # the lines to show, raw first; None when the source has no gold file
    warnings: Optional[list[str]] = None
    error: Optional[str] = None
    blocked: bool = False               # the site refuses automatic reading: offer a saved file


class SourceBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["heading", "text", "image"]
    text: str = ""
    anchor: Optional[str] = None
    image: Optional[str] = None         # file:// address of a picture kept on this PC
    web_image: Optional[str] = None     # https address of one a saved page left behind: the source window shows it from there


class SourceView(_Msg):          # shell/sourceView.ts
    """Where this step came from: a clip to play, text to read, or why neither is here."""
    type: Literal["source_view"] = "source_view"
    kind: Literal["video", "text", "none", "loading"]
    n: int
    of: int
    title: str
    tutorial: str
    follow: bool = False                # the step moved on while the window is open: no window of its own, no autoplay
    where: Optional[str] = None         # "01:39–01:44", or the section's heading
    video: Optional[str] = None         # file:// address
    start: Optional[float] = None       # seconds in that file
    end: Optional[float] = None
    doc: Optional[str] = None           # which text this is, so the window keeps it when only the section changes
    blocks: Optional[list[SourceBlock]] = None
    anchor: Optional[str] = None        # the section, among the blocks' anchors
    note: Optional[str] = None
    message: Optional[str] = None       # why the source isn't here
    link: Optional[str] = None          # http(s) only
    link_label: Optional[str] = None
    choose: Optional[Literal["video"]] = None    # offer to pick the video file on this PC


ToOverlay = Union[Guide, Clear, State, Toast, ShowMe, Mark, StartCheck, CompileProgress, CompileDone, SourceView]

# ---------------- overlay → engine ----------------


class Hello(_Msg):
    type: Literal["hello"] = "hello"
    displays: list[Display] = Field(default_factory=list)
    version: Optional[str] = None
    replay: bool = False


class _Simple(_Msg):
    pass


class ShowMeReq(_Simple):
    type: Literal["show_me"] = "show_me"


class DoIt(_Simple):
    type: Literal["do_it"] = "do_it"


class Next(_Simple):
    type: Literal["next"] = "next"


class Back(_Simple):
    type: Literal["back"] = "back"


class Skip(_Simple):
    type: Literal["skip"] = "skip"


class StartOk(_Simple):
    type: Literal["start_ok"] = "start_ok"


class UseWindow(_Simple):
    """The window in front is the tutorial's app."""
    type: Literal["use_window"] = "use_window"


class Hide(_Simple):
    type: Literal["hide"] = "hide"


class Resume(_Simple):
    type: Literal["resume"] = "resume"


class Jump(_Msg):
    type: Literal["jump"] = "jump"
    n: int


class PinReq(_Msg):
    """Dev: the mouse position when Ctrl+Alt+P was pressed, physical px. Two presses = one box."""
    type: Literal["pin"] = "pin"
    at: tuple[int, int]


class Unpin(_Simple):
    type: Literal["unpin"] = "unpin"


class Import(_Msg):
    type: Literal["import"] = "import"
    url: Optional[str] = None
    file: Optional[str] = None
    text: Optional[str] = None
    start: Optional[str] = None         # video: mm:ss
    end: Optional[str] = None


class OpenTutorial(_Msg):
    """Play a compiled file: the import screen's Play button."""
    type: Literal["open_tutorial"] = "open_tutorial"
    path: str


class SourceReq(_Msg):
    """Open the current step's source. `follow`: the window is open and the step moved on."""
    type: Literal["source"] = "source"
    follow: bool = False


class SourceFile(_Msg):
    """A copy of the source the person picked on this PC."""
    type: Literal["source_file"] = "source_file"
    path: str


class ToggleScheme(_Simple):
    """Force the other colours, or go back to choosing them from the app behind the target."""
    type: Literal["toggle_scheme"] = "toggle_scheme"


class ToggleLocal(_Simple):
    """Keep every picture of the screen on this PC, or let models look again."""
    type: Literal["toggle_local"] = "toggle_local"


class End(_Simple):
    """The person ended the tutorial: the overlay is quitting, and the engine stops too. Its place is already saved."""
    type: Literal["end"] = "end"


FromOverlay = Union[Hello, ShowMeReq, DoIt, Next, Back, Skip, Hide, Resume, Jump, PinReq, Unpin, Import, OpenTutorial, StartOk, UseWindow,
                    SourceReq, SourceFile, ToggleScheme, ToggleLocal, End]

TO_OVERLAY_TYPES = ("guide", "clear", "state", "toast", "show_me", "mark", "start_check", "compile_progress", "compile_done",
                    "source_view")
FROM_OVERLAY_TYPES = ("hello", "show_me", "do_it", "next", "back", "skip", "hide", "resume", "jump", "pin", "unpin", "import",
                      "open_tutorial", "start_ok", "use_window", "source", "source_file", "toggle_scheme", "toggle_local", "end")


def parse_from_overlay(raw: Union[str, bytes, dict]) -> FromOverlay:
    """Raises pydantic.ValidationError (or ValueError for bad JSON) on anything unknown."""
    data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    if not isinstance(data, dict) or data.get("type") not in FROM_OVERLAY_TYPES:
        raise ValueError(f"unknown overlay message: {str(data)[:80]}")
    # Discriminate by `type` (show_me exists in both directions; this is the request form).
    cls = {c.model_fields["type"].default: c for c in FromOverlay.__args__}[data["type"]]  # type: ignore[attr-defined]
    return cls.model_validate(data)


def dumps(msg: _Msg) -> str:
    return json.dumps(msg.to_wire(), ensure_ascii=False, separators=(",", ":"))
