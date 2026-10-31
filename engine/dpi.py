"""Per-monitor DPI awareness. UIA, mss, pyautogui and Electron must all agree
on physical pixels, so call this once at process start, before any window, UIA or screenshot call."""
from __future__ import annotations

import sys

_done = False


def make_dpi_aware() -> str:
    """Returns which API took effect: per-monitor-v2, per-monitor, system, or n/a off Windows."""
    global _done
    if sys.platform != "win32":
        return "n/a"
    import ctypes

    if _done:
        return "already"
    _done = True
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4 (Windows 10 1703+)
        if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return "per-monitor-v2"
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # PROCESS_PER_MONITOR_DPI_AWARE
        return "per-monitor"
    except (AttributeError, OSError):
        pass
    ctypes.windll.user32.SetProcessDPIAware()
    return "system"
