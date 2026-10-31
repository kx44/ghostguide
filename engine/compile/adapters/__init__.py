"""Source → evidence timeline. Each adapter reads one kind of source; all end up in one shape (timeline.Evidence)."""
from __future__ import annotations


class SourceError(RuntimeError):
    """The source can't be read. The message is written for the person importing it."""


class SourceBlocked(SourceError):
    """The site refuses automatic reading. We don't get around that: the person saves the page and drops the file."""
