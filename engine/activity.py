"""What GhostGuide sent and did, for you to read: one line per send or act, never its contents. And the switch that keeps
your screen on this PC.

    python -m engine activity

`cache/logs/activity.jsonl` says who was sent how many pictures and how many bytes, and which step Do it for me acted on.
It holds no pictures, no prompts, no typed text and no keys.
"""
from __future__ import annotations

import json
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from engine import config

LOG: Path = config.LOGS / "activity.jsonl"
SWITCH: Path = config.CACHE / "screen-stays-here"     # there while the tray's switch is on, so a restart doesn't undo it
SCREEN_TAGS = ("find-", "check-", "wonder-", "box-")     # a model call with these tags carries a picture of your screen
WITHHELD_EVERY_S = 60.0     # a window stays withheld for many rounds: one line a minute says so

# A window title that names one of these shows something that shouldn't leave the PC, whichever app it's in.
SECRET_TITLE = re.compile(r"(^|[\s/\\●•*-])\.(env(\.\w+)?|npmrc|netrc|pypirc|pgpass|htpasswd|dockercfg)\b"
                          r"|\bid_(rsa|ed25519|ecdsa|dsa)\b|\.(pem|pfx|p12|kdbx|key|ppk|tfvars)\b"
                          r"|\b(secrets?|credentials?|passwords?|private[ _-]?key|api[ _-]?keys?|kubeconfig)\b"
                          r"|\bappsettings(\.[\w-]+)*\.json\b|\b[\w-]*tokens?\.(txt|json|ya?ml)\b", re.I)
# These show your passwords or your money whatever else their title says.
SENSITIVE_APP = re.compile(r"\b(1password|bitwarden|lastpass|keepass(xc)?|dashlane|nordpass|enpass|roboform|proton ?pass)\b"
                           r"|\b(online|internet|mobile) banking\b", re.I)

_lock = threading.Lock()
_pictures = 0
_withheld_t: dict[str, float] = {}
_local_only = config.env("GG_LOCAL_ONLY", "off").lower() in ("on", "1", "true", "yes") or SWITCH.exists()


class LocalOnly(RuntimeError):
    """A picture of the screen was about to leave while it's set to stay on this PC."""


def local_only() -> bool:
    return _local_only


def set_local_only(on: bool) -> None:
    global _local_only
    _local_only = on


def switch_local_only() -> bool:
    """The tray's switch: flips it and remembers it for the next run. A file that can't be written mustn't stop the switch."""
    set_local_only(not _local_only)
    try:
        if _local_only:
            SWITCH.parent.mkdir(parents=True, exist_ok=True)
            SWITCH.touch()
        else:
            SWITCH.unlink(missing_ok=True)
    except OSError:
        pass
    return _local_only


def is_screen(tag: str) -> bool:
    return tag.startswith(SCREEN_TAGS)


def is_sensitive_app(name: Optional[str]) -> bool:
    """A password manager or a bank, by its window title or program name."""
    return bool(name and SENSITIVE_APP.search(name))


def title_withheld(title: Optional[str]) -> Optional[str]:
    """Why a window with this title must not go to a model, or None."""
    if title and SECRET_TITLE.search(title):
        return "its title names a secrets file"
    if is_sensitive_app(title):
        return "it's a password manager or a bank"
    return None


def host_of(url: str) -> str:
    return urlparse(url).netloc or url


def _write(entry: dict) -> None:
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with _lock, LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry}) + "\n")
    except OSError:
        pass        # a full disk mustn't stop a tutorial


def sent(to: str, model: str, tag: str, images: int, size: int) -> None:
    """Something left this PC. `size`: bytes of pictures or audio in it."""
    global _pictures
    screen = is_screen(tag)
    if screen:
        with _lock:
            _pictures += images
    _write({"kind": "sent", "to": to, "model": model, "tag": tag, "images": images, "bytes": size, "screen": screen})


def withheld(why: str, clock=time.monotonic) -> None:
    now = clock()
    if now - _withheld_t.get(why, -1e9) >= WITHHELD_EVERY_S:
        _withheld_t[why] = now
        _write({"kind": "withheld", "why": why})


def acted(step: int, title: str, ops: list[str]) -> None:
    """Do it for me acted. What kinds of input it sent, not the text."""
    _write({"kind": "acted", "step": step, "title": title, "ops": ops})


def pictures_sent() -> int:
    """Pictures of your screen sent since this engine started."""
    return _pictures


def privacy_line(models_on: bool) -> str:
    """The tray's plain statement of what's happening right now."""
    if local_only():
        return "Nothing from your screen leaves this PC"
    if not models_on:
        return "Model looks are off: nothing from your screen leaves this PC"
    n = pictures_sent()
    return f"{n} picture{'' if n == 1 else 's'} of this app sent to a model this run"


def read() -> list[dict]:
    if not LOG.exists():
        return []
    out = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out
