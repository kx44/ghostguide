"""Tutorial, Step, Target, Verify: the base-file contract."""
from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

Action = Literal["click", "draw_line", "drag", "type", "shortcut", "pick",
                 "menu_path", "switch_app", "wait", "look"]
Kind = Literal["button", "tab", "menu_item", "field", "tree_item",
               "face", "edge", "canvas", "window"]
Confidence = Literal["high", "low", "inferred"]
SourceType = Literal["video", "web", "pdf", "text"]

# action → guidance style number. 9 and 11 are decided at runtime.
ACTION_STYLE = {
    "click": 1, "draw_line": 2, "drag": 2, "type": 5, "shortcut": 6, "pick": 7,
    "menu_path": 8, "switch_app": 10, "wait": 12, "look": None,
}

# UI Automation control types a `verify.uia.type` may name (ControlType without the "Control" suffix).
UIA_TYPES = {
    "AppBar", "Button", "Calendar", "CheckBox", "ComboBox", "Custom", "DataGrid", "DataItem",
    "Document", "Edit", "Group", "Header", "HeaderItem", "Hyperlink", "Image", "List",
    "ListItem", "Menu", "MenuBar", "MenuItem", "Pane", "ProgressBar", "RadioButton",
    "ScrollBar", "SemanticZoom", "Separator", "Slider", "Spinner", "SplitButton", "StatusBar",
    "Tab", "TabItem", "Table", "Text", "Thumb", "TitleBar", "ToolBar", "ToolTip", "Tree",
    "TreeItem", "Window",
}


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Target(_Strict):
    label: str
    kind: Kind
    where: Optional[str] = None
    crop: Optional[str] = None
    menu_path: Optional[list[str]] = None
    aliases: Optional[list[str]] = None
    shortcut: Optional[str] = None


class Source(_Strict):
    t: Optional[str] = None        # "mm:ss" or "mm:ss-mm:ss" (video)
    anchor: Optional[str] = None   # "#section" (web)

    @model_validator(mode="after")
    def _one(self):
        if not (self.t or self.anchor):
            raise ValueError("source needs `t` or `anchor`")
        return self


class UiaCheck(_Strict):
    """One accessibility fact that must hold when the step is done. All given fields must match."""
    name: Optional[str] = None            # exact element name
    name_contains: Optional[str] = None
    type: Optional[str] = None            # UIA control type, e.g. TabItem, Edit, Window
    value: Optional[str] = None           # ValuePattern value, exact
    value_contains: Optional[str] = None
    window: Optional[str] = None          # top-level window title contains this (scopes the search)
    selected: Optional[bool] = None       # SelectionItem / tab selected
    exists: bool = True                   # false = the element must be gone

    @model_validator(mode="after")
    def _identifies_something(self):
        if not (self.name or self.name_contains or self.type):
            raise ValueError("uia check needs name, name_contains or type")
        if self.type and self.type not in UIA_TYPES:
            raise ValueError(f"unknown UIA control type {self.type!r}")
        return self


class FileCheck(_Strict):
    """A fact about a file on disk, relative to the tutorial's working folder."""
    path: str
    contains: Optional[str] = None
    not_contains: Optional[str] = None
    exists: bool = True


class Verify(_Strict):
    """Machine-checkable version of `check` (live step 9a). Every listed check must hold."""
    uia: Optional[Union[UiaCheck, list[UiaCheck]]] = None
    file: Optional[Union[FileCheck, list[FileCheck]]] = None

    @model_validator(mode="after")
    def _not_empty(self):
        if self.uia is None and self.file is None:
            raise ValueError("verify needs `uia` or `file`")
        return self

    def uia_checks(self) -> list[UiaCheck]:
        return [] if self.uia is None else (self.uia if isinstance(self.uia, list) else [self.uia])

    def file_checks(self) -> list[FileCheck]:
        return [] if self.file is None else (self.file if isinstance(self.file, list) else [self.file])


# Keys in the order they are written in a step's YAML block.
STEP_KEYS = ("app", "action", "target", "params", "why", "check", "verify", "source",
             "confidence", "repeat_of", "optional", "simplified", "note")


class Step(_Strict):
    n: int = Field(exclude=True)                  # from the heading, not the YAML
    title: str = Field(exclude=True)
    part: Optional[str] = Field(default=None, exclude=True)   # the `# Part …` heading above it

    app: Optional[str] = None                     # the program this step happens in, when it isn't the tutorial's own
    action: Action
    target: Target
    params: dict[str, Any] = Field(default_factory=dict)
    why: Optional[str] = None
    check: str
    verify: Optional[Verify] = None
    source: Source
    confidence: Optional[Confidence] = None       # may be left out on repeats
    repeat_of: Optional[int] = None
    optional: Optional[bool] = None
    simplified: Optional[str] = None
    note: Optional[str] = None

    # The YAML block as read from disk, so an unchanged step renders byte-for-byte (keeps comments).
    _raw: Optional[str] = PrivateAttr(default=None)
    _raw_data: Optional[dict] = PrivateAttr(default=None)

    def yaml_data(self) -> dict:
        """The step's YAML block as plain data, in STEP_KEYS order, without empty fields."""
        dumped = self.model_dump(mode="json", exclude_none=True)
        if not dumped.get("params"):
            dumped.pop("params", None)
        return {k: dumped[k] for k in STEP_KEYS if k in dumped}

    @property
    def style(self) -> Optional[int]:
        return ACTION_STYLE[self.action]


class SourceInfo(BaseModel):
    model_config = ConfigDict(extra="allow")      # author, published, segment, chapters…
    type: SourceType
    url: Optional[str] = None
    hash: Optional[str] = None


class TutorialMeta(BaseModel):
    model_config = ConfigDict(extra="allow")      # verified, notes… kept for the round trip
    title: str
    app: str
    author_version: Optional[str] = None
    source: SourceInfo
    start_state: Optional[str] = None
    units: Optional[str] = None
    gold: bool = False


class Tutorial(BaseModel):
    meta: TutorialMeta
    steps: list[Step]

    _raw_frontmatter: Optional[str] = PrivateAttr(default=None)
    _raw_meta: Optional[dict] = PrivateAttr(default=None)

    def step(self, n: int) -> Step:
        return self.steps[n - 1]
