"""Do it for me (live step 8): the engine does the step with real input, through the same box the outline is on.

Only buttons, menus, fields and shortcuts: never drawing on the canvas, where a guess makes a wrong model. Offered
only when there's something sure to act on. A box from accessibility data is exact, so it just runs; a box Spark
found by sight first asks you to look (`needs_confirm`): the first press says so, the second one runs it.

Input only ever goes to the app: it refuses unless the app is the front window and the spot it would click is the
app's own. The pure part (what to do) is tested off Windows; everything that sends input is under `# ---- Windows`.
"""
from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from typing import Optional

from engine.schema.messages import Box
from engine.schema.tutorial import Step

DOABLE = {"click", "type", "shortcut", "menu_path"}
NOT_DOABLE_KINDS = {"canvas", "edge", "face"}
SURE_STAGES = {"uia"}
SETTLE_S = 0.15
RENAME_SETTLE_S = 0.5
HIT_SETTLE_S = 0.1       # the overlay checks the cursor every 30 ms and lets go of the mouse once it's off a card


@dataclass
class Op:
    kind: str                         # click | keys | text
    at: Optional[tuple[int, int]] = None
    button: str = "left"
    count: int = 1
    modifiers: tuple[str, ...] = ()
    keys: tuple[str, ...] = ()
    text: str = ""


def _value(step: Step) -> Optional[str]:
    p = step.params
    v = p.get("value")
    if v is None and isinstance(p.get("suggested"), dict):
        v = p["suggested"].get("value")
    return None if v is None else str(v)


def can_do(step: Step, box: Optional[Box]) -> bool:
    """Is there something sure to act on, right now?"""
    if step.action not in DOABLE or step.target.kind in NOT_DOABLE_KINDS:
        return False
    if step.action == "shortcut":
        return bool(step.params.get("keys"))
    if step.action == "menu_path":          # a route of several clicks is yours; its shortcut is one key press
        return bool(step.target.shortcut)
    if step.action == "type":
        return box is not None and _value(step) is not None
    return box is not None or bool(step.target.shortcut)     # no box, but one key press does the same


def needs_confirm(step: Step, stage: str, box: Optional[Box] = None) -> bool:
    """A shortcut needs no box; UIA's box is exact; anything found by sight or memory waits for a second press."""
    return (box is not None and step.action not in ("shortcut", "menu_path") and stage not in SURE_STAGES)


def plan(step: Step, box: Optional[Box]) -> list[Op]:
    from engine.live.plan import click_type, line_start

    p = step.params
    if step.action == "shortcut":
        return [Op("keys", keys=tuple(str(k) for k in p["keys"]))]
    if step.action == "menu_path":
        return [Op("keys", keys=tuple(k.strip() for k in step.target.shortcut.split("+")))]
    if step.action == "type":
        ops = [Op("click", at=box.center)]
        ops.append(Op("keys", keys=("F2",)) if step.target.kind == "tree_item" else Op("keys", keys=("Ctrl", "A")))
        ops.append(Op("text", text=_value(step)))
        then = p.get("then_key") or ("Tab" if step.target.kind == "field" else None)    # Tab commits a number without pressing OK
        if then:
            ops.append(Op("keys", keys=(str(then),)))
        return ops
    if box is None:
        return [Op("keys", keys=tuple(k.strip() for k in step.target.shortcut.split("+")))]
    ct = click_type(p) or {}
    return [Op("click", at=box.center, button=ct.get("button", "left"), count=ct.get("count", 1),
               modifiers=tuple(ct.get("modifiers", ())))]


def say_done(step: Step) -> str:
    return f"Done for you: {step.title}."


# ---------- Windows -------------------------------------------------------------------------------
VK = {"ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12, "esc": 0x1B, "escape": 0x1B, "enter": 0x0D, "return": 0x0D,
      "tab": 0x09, "space": 0x20, "f2": 0x71, "del": 0x2E, "delete": 0x2E}


def _vk(key: str) -> int:
    k = key.strip().casefold()
    if k in VK:
        return VK[k]
    if len(k) == 1 and k.isalnum():
        return ord(k.upper())
    raise ValueError(f"unknown key {key!r}")


class Executor:
    def __init__(self, app_window: str):
        self.app_window = app_window

    def _app_pid(self) -> Optional[int]:
        from engine.live import windows
        w = windows.find(self.app_window)
        return _pid(w.hwnd) if w else None

    def refuse(self, ops: list[Op]) -> Optional[str]:
        """Why not to send this input, or None. Checked right before sending, never from memory."""
        from engine.live import windows
        pid = self._app_pid()
        if pid is None:
            return f"{self.app_window} isn't open."
        fg = windows.foreground()
        if fg is None or _pid(fg.hwnd) != pid:
            return f"Bring {self.app_window} to the front first, so nothing goes to another window."
        for op in ops:
            if op.kind == "click":
                # From there, not from here: the cursor is on our card, whose overlay takes the mouse until it leaves.
                ctypes_set_cursor(op.at)
                time.sleep(HIT_SETTLE_S)
                if _pid_at(op.at) != pid:
                    return "Something is covering that spot, so nothing was clicked."
        return None

    def run(self, ops: list[Op]) -> Optional[str]:
        """Sends the input. → why it refused, or None once it's done."""
        if sys.platform != "win32":
            return "Do it for me needs Windows."
        why = self.refuse(ops)
        if why:
            return why
        import ctypes
        u32 = ctypes.windll.user32
        back = _cursor()
        try:
            for op in ops:
                why = self.refuse([op])          # the app can open a dialog or lose focus between two inputs
                if why:
                    return why
                if op.kind == "click":
                    _click(op)
                elif op.kind == "keys":
                    _keys(op.keys)
                    if op.keys == ("F2",):
                        time.sleep(RENAME_SETTLE_S)       # the rename box takes a moment; typed sooner, it's lost
                elif op.kind == "text":
                    _text(op.text)
                time.sleep(SETTLE_S)
        finally:
            u32.SetCursorPos(*back)
        return None


def ctypes_set_cursor(at: tuple[int, int]) -> None:
    import ctypes
    ctypes.windll.user32.SetCursorPos(*at)


def _pid(hwnd: int) -> int:
    import ctypes
    import ctypes.wintypes as wt
    p = wt.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
    return p.value


def _pid_at(at: tuple[int, int]) -> int:
    import ctypes
    import ctypes.wintypes as wt
    u32 = ctypes.windll.user32
    u32.WindowFromPoint.argtypes = [wt.POINT]
    u32.WindowFromPoint.restype = wt.HWND
    h = u32.WindowFromPoint(wt.POINT(*at))
    return _pid(h) if h else 0


def _cursor() -> tuple[int, int]:
    import ctypes
    import ctypes.wintypes as wt
    p = wt.POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def _click(op: Op) -> None:
    import ctypes
    u32 = ctypes.windll.user32
    down, up = (8, 16) if op.button == "right" else (2, 4)      # MOUSEEVENTF_{RIGHT,LEFT}{DOWN,UP}
    u32.SetCursorPos(*op.at)
    time.sleep(0.12)                                            # let the app's hover catch up, or it ignores the click
    for m in op.modifiers:
        u32.keybd_event(_vk(m), 0, 0, 0)
    for _ in range(op.count):
        u32.mouse_event(down, 0, 0, 0, 0)
        u32.mouse_event(up, 0, 0, 0, 0)
        time.sleep(0.05)
    for m in reversed(op.modifiers):
        u32.keybd_event(_vk(m), 0, 2, 0)


def _keys(keys: tuple[str, ...]) -> None:
    import ctypes
    u32 = ctypes.windll.user32
    vks = [_vk(k) for k in keys]
    for v in vks:
        u32.keybd_event(v, 0, 0, 0)
    for v in reversed(vks):
        u32.keybd_event(v, 0, 2, 0)


def _text(text: str) -> None:
    """Characters as typed text (KEYEVENTF_UNICODE), so the keyboard layout doesn't matter."""
    import ctypes
    import ctypes.wintypes as wt

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                    ("dwExtraInfo", ctypes.c_size_t)]

    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wt.DWORD), ("u", _U)]

    for ch in text:
        for flags in (4, 4 | 2):                 # KEYEVENTF_UNICODE, + KEYUP
            i = INPUT(type=1)
            i.u.ki = KEYBDINPUT(0, ord(ch), flags, 0, 0)
            ctypes.windll.user32.SendInput(1, ctypes.byref(i), ctypes.sizeof(INPUT))
        time.sleep(0.01)
