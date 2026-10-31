"""Our computer-use tools. The model calls them with screenshot coordinates; we draw instead of clicking."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional, Union


def _fn(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required},
    }}


_INT = {"type": "integer"}
_CONF = {"type": "string", "enum": ["high", "low"]}

POINT_AT = _fn(
    "point_at", "Point at the on-screen control that matches the description. x, y = the center of the control; "
    "w, h = its width and height. Screenshot pixels, (0, 0) = top-left corner.",
    {"x": _INT, "y": _INT, "w": _INT, "h": _INT, "label_seen": {"type": "string"}, "confidence": _CONF},
    ["x", "y", "w", "h", "confidence"])
DRAW_LINE = _fn(
    "draw_line", "Show a cursor action from one point to another (draw, drag). Screenshot pixels.",
    {"x1": _INT, "y1": _INT, "x2": _INT, "y2": _INT, "confidence": _CONF},
    ["x1", "y1", "x2", "y2", "confidence"])
MENU_PATH = _fn(
    "menu_path", "The control is not visible; give the menu route that reaches it, top level first.",
    {"path": {"type": "array", "items": {"type": "string"}}, "confidence": _CONF},
    ["path", "confidence"])
NOT_FOUND = _fn(
    "not_found", "The control is not on screen and no route is known.",
    {"reason": {"type": "string"}}, ["reason"])

LOCATE_TOOLS = [POINT_AT, DRAW_LINE, MENU_PATH, NOT_FOUND]
WEB_SEARCH = {"type": "web_search"}   # Meta built-in tool, used by enrichment


@dataclass
class PointAt:
    x: int          # center of the control (Spark answers centers; tested 31 Oct), screenshot px
    y: int
    w: int
    h: int
    confidence: str
    label_seen: Optional[str] = None


@dataclass
class DrawLine:
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: str


@dataclass
class MenuPath:
    path: list[str]
    confidence: str


@dataclass
class NotFound:
    reason: str


ToolCall = Union[PointAt, DrawLine, MenuPath, NotFound]
_TYPES = {"point_at": PointAt, "draw_line": DrawLine, "menu_path": MenuPath, "not_found": NotFound}


def parse_tool_call(name: str, arguments: Union[str, dict]) -> ToolCall:
    args = json.loads(arguments) if isinstance(arguments, str) else dict(arguments)
    if name not in _TYPES:
        raise ValueError(f"unknown tool {name!r}")
    cls = _TYPES[name]
    allowed = cls.__dataclass_fields__
    return cls(**{k: v for k, v in args.items() if k in allowed})
