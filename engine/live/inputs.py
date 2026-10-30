"""Global input watcher (live step 9's trigger): what happened, where, when. **Never the keys typed**: a key
press is recorded as the kind "key" and its key code is dropped where it arrives. Typed values are checked
through accessibility (live/verify.py), not from here.

It uses Raw Input (RegisterRawInputDevices with RIDEV_INPUTSINK) on a hidden window of its own thread. Raw
Input is a copy Windows hands us; it doesn't sit in the input chain like a low-level hook, so a busy engine
can never slow down your typing or clicks, and nothing can be swallowed. Events feed:
- the step checks: a click or a pause after typing wakes the checker now instead of at the next tick;
- settle: "no keys or clicks for 1.2 s" before a typing step counts as done;
- card placement: where you've been clicking recently (the card keeps out of the way).
"""
from __future__ import annotations

import sys
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Literal, Optional

Kind = Literal["down", "up", "wheel", "key", "move"]
MOVE_EVERY_S = 0.1        # mouse moves are kept at most this often (a gaming mouse reports 1000/s)
KEEP = 400                # recent events kept


@dataclass(frozen=True)
class InputEvent:
    kind: Kind
    x: int
    y: int
    t: float              # time.monotonic()
    button: str = ""      # left | right | middle for down / up


class Recent:
    """The recent events, plus the derived facts the engine asks for. Pure, so it's unit-tested."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self.events: deque[InputEvent] = deque(maxlen=KEEP)
        self.clock = clock
        self.last_key_or_click = 0.0
        self._last_move = 0.0
        self.listeners: list[Callable[[InputEvent], None]] = []
        self._lock = threading.Lock()

    def add(self, ev: InputEvent) -> None:
        if ev.kind == "move":
            if ev.t - self._last_move < MOVE_EVERY_S:
                return
            self._last_move = ev.t
        with self._lock:
            self.events.append(ev)
            if ev.kind in ("down", "key", "wheel"):
                self.last_key_or_click = ev.t
        for cb in list(self.listeners):
            try:
                cb(ev)
            except Exception:
                pass

    def idle_s(self) -> float:
        """Seconds since the last key, click or wheel (moves don't count: hovering isn't working)."""
        return self.clock() - self.last_key_or_click if self.last_key_or_click else 1e9

    def clicks(self, within_s: float = 20.0) -> list[InputEvent]:
        now = self.clock()
        with self._lock:
            return [e for e in self.events if e.kind == "down" and now - e.t <= within_s]

    def work_area(self, within_s: float = 20.0, pad: int = 80) -> Optional[tuple[int, int, int, int]]:
        """The box around your recent clicks, padded: where you're working. None without recent clicks."""
        cs = self.clicks(within_s)
        if not cs:
            return None
        x0, y0 = min(e.x for e in cs) - pad, min(e.y for e in cs) - pad
        x1, y1 = max(e.x for e in cs) + pad, max(e.y for e in cs) + pad
        return x0, y0, x1 - x0, y1 - y0


# ---------- Windows: Raw Input on a hidden window ---------------------------------------------------
_BUTTONS = ((0x0001, "down", "left"), (0x0002, "up", "left"), (0x0004, "down", "right"), (0x0008, "up", "right"),
            (0x0010, "down", "middle"), (0x0020, "up", "middle"))


class Watcher:
    """Starts the Raw Input thread; `recent` fills as you use the mouse and keyboard."""

    def __init__(self, recent: Optional[Recent] = None):
        self.recent = recent or Recent()
        self._thread: Optional[threading.Thread] = None
        self.error: Optional[str] = None
        self._hwnd = 0

    def start(self) -> "Watcher":
        if sys.platform != "win32":
            self.error = "input watcher needs Windows"
            return self
        self._thread = threading.Thread(target=self._run, name="ghost-inputs", daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._hwnd:
            import ctypes
            ctypes.windll.user32.PostMessageW(self._hwnd, 0x0010, 0, 0)     # WM_CLOSE

    def _run(self) -> None:
        try:
            self._loop()
        except Exception as e:          # never take the engine down with it
            self.error = f"input watcher stopped: {e}"

    def _loop(self) -> None:
        import ctypes
        import ctypes.wintypes as wt

        u32 = ctypes.windll.user32
        k32 = ctypes.windll.kernel32
        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
        u32.DefWindowProcW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
        u32.DefWindowProcW.restype = LRESULT

        class RAWINPUTHEADER(ctypes.Structure):
            _fields_ = [("dwType", wt.DWORD), ("dwSize", wt.DWORD), ("hDevice", wt.HANDLE), ("wParam", wt.WPARAM)]

        class RAWMOUSE(ctypes.Structure):
            # the button fields sit in a union aligned to 4 bytes, so 2 bytes of padding follow usFlags
            _fields_ = [("usFlags", wt.USHORT), ("_pad", wt.USHORT), ("usButtonFlags", wt.USHORT), ("usButtonData", wt.USHORT),
                        ("ulRawButtons", wt.ULONG), ("lLastX", wt.LONG), ("lLastY", wt.LONG),
                        ("ulExtraInformation", wt.ULONG)]

        class RAWKEYBOARD(ctypes.Structure):
            _fields_ = [("MakeCode", wt.USHORT), ("Flags", wt.USHORT), ("Reserved", wt.USHORT),
                        ("VKey", wt.USHORT), ("Message", wt.UINT), ("ExtraInformation", wt.ULONG)]

        class _U(ctypes.Union):
            _fields_ = [("mouse", RAWMOUSE), ("keyboard", RAWKEYBOARD)]

        class RAWINPUT(ctypes.Structure):
            _fields_ = [("header", RAWINPUTHEADER), ("data", _U)]

        class RAWINPUTDEVICE(ctypes.Structure):
            _fields_ = [("usUsagePage", wt.USHORT), ("usUsage", wt.USHORT), ("dwFlags", wt.DWORD), ("hwndTarget", wt.HWND)]

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [("style", wt.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                        ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                        ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR),
                        ("lpszClassName", wt.LPCWSTR)]

        u32.GetRawInputData.argtypes = [wt.HANDLE, wt.UINT, ctypes.c_void_p, ctypes.POINTER(wt.UINT), wt.UINT]
        hdr_size = ctypes.sizeof(RAWINPUTHEADER)
        buf = RAWINPUT()
        pt = wt.POINT()
        recent = self.recent

        def proc(hwnd, msg, wparam, lparam):
            if msg == 0x00FF:                                  # WM_INPUT
                size = wt.UINT(ctypes.sizeof(buf))
                if u32.GetRawInputData(lparam, 0x10000003, ctypes.byref(buf), ctypes.byref(size), hdr_size) > 0:
                    now = time.monotonic()
                    if buf.header.dwType == 0:                 # mouse
                        u32.GetCursorPos(ctypes.byref(pt))
                        flags = buf.data.mouse.usButtonFlags
                        hit = False
                        for bit, kind, button in _BUTTONS:
                            if flags & bit:
                                recent.add(InputEvent(kind, pt.x, pt.y, now, button))
                                hit = True
                        if flags & 0x0400:                     # wheel
                            recent.add(InputEvent("wheel", pt.x, pt.y, now))
                        elif not hit:
                            recent.add(InputEvent("move", pt.x, pt.y, now))
                    elif buf.header.dwType == 1:               # keyboard: key-downs only, key code dropped here
                        if not (buf.data.keyboard.Flags & 1):  # RI_KEY_BREAK = key up
                            u32.GetCursorPos(ctypes.byref(pt))
                            recent.add(InputEvent("key", pt.x, pt.y, now))
                        buf.data.keyboard.VKey = 0
                        buf.data.keyboard.MakeCode = 0
                return 0
            if msg == 0x0010:                                  # WM_CLOSE
                u32.DestroyWindow(hwnd)
                return 0
            if msg == 0x0002:                                  # WM_DESTROY
                u32.PostQuitMessage(0)
                return 0
            return u32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._proc = WNDPROC(proc)                             # keep a reference: ctypes callbacks die with it
        hinst = k32.GetModuleHandleW(None)
        wc = WNDCLASSW(0, self._proc, 0, 0, hinst, None, None, None, None, "GhostGuideInputs")
        u32.RegisterClassW(ctypes.byref(wc))
        u32.CreateWindowExW.restype = wt.HWND
        hwnd = u32.CreateWindowExW(0, "GhostGuideInputs", "GhostGuide inputs", 0, 0, 0, 0, 0, None, None, hinst, None)
        if not hwnd:
            raise OSError("CreateWindowEx failed")
        self._hwnd = hwnd
        devs = (RAWINPUTDEVICE * 2)(RAWINPUTDEVICE(1, 2, 0x100, hwnd),    # mouse, RIDEV_INPUTSINK
                                    RAWINPUTDEVICE(1, 6, 0x100, hwnd))    # keyboard
        if not u32.RegisterRawInputDevices(devs, 2, ctypes.sizeof(RAWINPUTDEVICE)):
            raise OSError("RegisterRawInputDevices failed")
        msg = wt.MSG()
        while u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            u32.TranslateMessage(ctypes.byref(msg))
            u32.DispatchMessageW(ctypes.byref(msg))
