"""Glue between the session, the planner and the overlay, with no transport: one overlay message in →
the list of messages to send back. `engine/server.py` carries them over the WebSocket; tests and the
console mode call this directly.

Phase 2 finds targets from pinned boxes only (locate/pinned.py). Phase 3 swaps in the resolver.
"""
from __future__ import annotations

from typing import Callable, Optional

from pydantic import ValidationError

from engine.live.locate.pinned import Pins
from engine.live.plan import Planner
from engine.live.session import Event, Session
from engine.schema import messages as m

SchemeFn = Callable[[Optional[m.Box]], tuple[str, Optional[float]]]


class Player:
    def __init__(self, session: Session, pins: Optional[Pins] = None, scheme_fn: Optional[SchemeFn] = None,
                 scheme_override: Optional[str] = None, before_capture: Optional[Callable[[], None]] = None):
        self.session = session
        self.planner = Planner(session.tutorial)
        self.pins = pins or Pins()
        self.displays: list[m.Display] = []
        self.scheme_override = scheme_override
        self._scheme_fn = scheme_fn
        self.before_capture = before_capture     # the server clears the overlay before a ring grab
        self.scheme = scheme_override or "dark"
        self._scheme_cache: dict[tuple, str] = {}
        self.last_guide: Optional[m.Guide] = None

    # ---------- what's on screen now ----------
    def target(self, n: int) -> tuple[Optional[m.Box], Optional[m.Line]]:
        return self.pins.box(n), self.pins.line(n)

    def _scheme(self, box: Optional[m.Box]) -> str:
        if self.scheme_override:
            return self.scheme_override
        if self._scheme_fn is None:
            return self.scheme
        key = (box.x, box.y, box.w, box.h) if box else None
        if key in self._scheme_cache:
            return self._scheme_cache[key]
        if box is not None and self.before_capture:
            self.before_capture()
        scheme, _ = self._scheme_fn(box)
        self._scheme_cache[key] = scheme
        return scheme

    def current(self) -> list[m._Msg]:
        """The full picture: step rail state, then the guide (or a clear when hidden / finished)."""
        s = self.session
        out: list[m._Msg] = []
        guide: Optional[m.Guide] = None
        if not s.finished and not s.hidden:
            step = s.step
            assert step is not None
            box, line = self.target(step.n)
            self.scheme = self._scheme(box)
            guide = self.planner.plan(step, box, line, self.displays, self.scheme)
        out.append(self.state())
        if guide is None:
            out.append(m.Clear(reason="finished" if s.finished else "hidden"))
        else:
            out.append(guide)
        self.last_guide = guide
        return out

    def state(self) -> m.State:
        s = self.session
        return m.State(tutorial=s.tutorial.meta.title, current=s.current, of=s.of, hidden=s.hidden,
                       finished=s.finished, titles=[st.title for st in s.tutorial.steps],
                       statuses=list(s.statuses), scheme=self.scheme)

    # ---------- one message in ----------
    def handle(self, raw) -> list[m._Msg]:
        try:
            msg = m.parse_from_overlay(raw)
        except (ValueError, ValidationError) as e:
            return [m.Toast(text=f"Engine ignored a bad message: {str(e)[:80]}", kind="warn")]
        s = self.session
        t = msg.type
        if t == "hello":
            self.displays = list(msg.displays)
            self._scheme_cache.clear()
            return self.current()
        if t == "show_me":
            if s.finished or s.hidden or s.step is None:
                return []
            box, line = self.target(s.step.n)
            sm = self.planner.show_me(s.step, box, line)
            return [sm] if sm else [m.Toast(text="No target pinned for this step, so nothing to show.", kind="warn")]
        if t == "do_it":
            return [m.Toast(text="Do it for me arrives in phase 4.", kind="warn")]
        if t == "import":
            return [m.Toast(text="Importing tutorials arrives in phase 5.", kind="warn")]
        if t == "next":
            had_target = self.last_guide is not None and self.last_guide.box is not None
            ev = s.next()
            return ([m.Mark(result="ok")] if had_target and ev.kind != "noop" else []) + self._after(ev)
        if t == "back":
            return self._after(s.back())
        if t == "skip":
            return self._after(s.skip())
        if t == "jump":
            try:
                return self._after(s.jump(msg.n))
            except ValueError as e:
                return [m.Toast(text=str(e), kind="warn")]
        if t == "hide":
            return self._after(s.hide())
        if t == "resume":
            return self._after(s.resume())
        return []

    def _after(self, ev: Event) -> list[m._Msg]:
        if ev.kind == "noop":
            return []
        out = self.current()
        if ev.text:
            out.append(m.Toast(text=ev.text, kind="warn" if ev.kind == "skipped" else "ok",
                               ms=3000 if ev.kind in ("finished", "caught_up") else 2000))
        return out
