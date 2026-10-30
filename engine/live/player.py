"""Glue between the session, the planner and the overlay, with no transport: one overlay message in →
the list of messages to send back. `engine/server.py` carries them over the WebSocket; tests and the
console mode call this directly.

Phase 2 finds targets from pinned boxes (locate/pinned.py), else from a locator such as the VS Code UIA
rules (locate/vscode.py); a pin always wins. Phase 3 swaps in the resolver.
"""
from __future__ import annotations

from typing import Callable, Optional, Protocol

from pydantic import ValidationError

from engine.live.locate.pinned import Pin, Pins
from engine.live.plan import Planner
from engine.live.session import Event, Session
from engine.schema import messages as m

# Steps that need no on-screen target (their card alone is the guidance), so no "not pinned" hint.
NO_PIN_NEEDED = {"shortcut", "wait", "look"}
LINE_ACTIONS = {"draw_line", "drag"}

SchemeFn = Callable[[Optional[m.Box]], tuple[str, Optional[float]]]


class Locator(Protocol):
    last_how: str                                # which rule hit, or why nothing did

    def locate(self, step) -> tuple[Optional[m.Box], Optional[m.Line]]: ...


class Player:
    def __init__(self, session: Session, pins: Optional[Pins] = None, scheme_fn: Optional[SchemeFn] = None,
                 scheme_override: Optional[str] = None, before_capture: Optional[Callable[[], None]] = None,
                 pins_path=None, locator: Optional[Locator] = None):
        self.session = session
        # Finds targets live. Slow (a UIA walk), so it never runs inside handle(): the server calls
        # locate_current() outside its lock and apply_located() with the result, so buttons answer at once.
        self.locator = locator
        self._located: dict[int, tuple[Optional[m.Box], Optional[m.Line]]] = {}
        self._located_extra: dict[int, dict] = {}   # e.g. editor clip + backing colour for ghost text
        self.pins_path = pins_path               # where Ctrl+Alt+P pins are saved; None = keep in memory
        self._corner: Optional[tuple[int, int]] = None   # first Ctrl+Alt+P of a pair
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
        """Pin first, else where the locator last found it (nothing yet = card only until it reports)."""
        box, line = self.pins.box(n), self.pins.line(n)
        if box is None and line is None:
            box, line = self._located.get(n, (None, None))
        return box, line

    def _scheme(self, box: Optional[m.Box], n: Optional[int] = None) -> str:
        if self.scheme_override:
            return self.scheme_override
        if self._scheme_fn is None:
            return self.scheme
        # A located box moves with the caret; the app behind it doesn't change within a step, so measure once.
        key = ("step", n) if self.locator is not None and n is not None else (box.x, box.y, box.w, box.h) if box else None
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
            self.scheme = self._scheme(box, step.n)
            guide = self.planner.plan(step, box, line, self.displays, self.scheme)
            if guide.style in ("code_card", "ghost_text") and step.n not in self.pins.steps:
                guide.extra.update(self._located_extra.get(step.n, {}))
            if guide.card is not None and box is None and step.action not in NO_PIN_NEEDED:
                first = "start point" if step.action in LINE_ACTIONS else "top-left corner"
                second = "end point" if step.action in LINE_ACTIONS else "bottom-right corner"
                found = ("Not pinned yet: " if self.locator is None else
                         f"Not found ({self.locator.last_how}). " if step.n in self._located else "Looking for it… ")
                guide.card.dev_hint = (f"{found}Hover the {first} of {step.target.label} and press "
                                       f"Ctrl+Alt+P, then the {second} and Ctrl+Alt+P again." if self._corner is None
                                       else f"Now hover the {second} and press Ctrl+Alt+P.")
        out.append(self.state())
        if guide is None:
            out.append(m.Clear(reason="finished" if s.finished else "hidden"))
        else:
            out.append(guide)
        self.last_guide = guide
        return out

    def locate_current(self) -> Optional[tuple]:
        """Ask the locator about the current step: (step, box, line, extra), or None when there's nothing to ask.
        Reads the session but changes nothing, so the server runs it outside its lock."""
        s = self.session
        if self.locator is None or s.finished or s.hidden or s.step is None or s.step.n in self.pins.steps:
            return None
        step = s.step
        try:
            box, line = self.locator.locate(step)
        except Exception as e:      # UIA hiccups (window closing, element gone) must not end the session
            self.locator.last_how = f"locator error: {e}"
            box, line = None, None
        return step.n, box, line, dict(getattr(self.locator, "last_extra", None) or {})

    def apply_located(self, found) -> list[m._Msg]:
        """Store a locate_current() result; the guide again when the target moved, appeared or went away
        on the step still showing, else nothing (the user may have moved on meanwhile)."""
        if found is None:
            return []
        n, box, line = found[:3]
        first = n not in self._located
        self._located[n] = (box, line)
        self._located_extra[n] = found[3] if len(found) > 3 else {}
        s = self.session
        if s.finished or s.hidden or s.step is None or s.step.n != n:
            return []
        g = self.last_guide
        if not first and g is not None and g.step.n == n and g.line == line and _near(g.box, box):
            self._located[n] = (g.box, g.line)    # keep what's drawn: a pixel of jitter mustn't move the card
            return []
        return self.current()

    def refresh(self) -> list[m._Msg]:
        """locate_current + apply_located in one go (tests, console mode)."""
        return self.apply_located(self.locate_current())

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
        if t == "pin":
            return self._pin(msg.at)
        if t == "unpin":
            if s.finished or s.step is None or s.step.n not in self.pins.steps:
                return []
            del self.pins.steps[s.step.n]
            self._corner = None
            self._save_pins()
            return self.current() + [m.Toast(text=f"Pin removed from step {s.step.n}.", kind="warn")]
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

    def _pin(self, at: tuple[int, int]) -> list[m._Msg]:
        s = self.session
        if s.finished or s.hidden or s.step is None:
            return []
        if self._corner is None:
            self._corner = at
            out = self.current()
            what = "Start point" if s.step.action in LINE_ACTIONS else "Top-left"
            return out + [m.Toast(text=f"{what} saved. Now the other corner, Ctrl+Alt+P.", ms=2500)]
        (x1, y1), (x2, y2) = self._corner, at
        self._corner = None
        if s.step.action in LINE_ACTIONS:
            self.pins.steps[s.step.n] = Pin(line=((x1, y1), (x2, y2)))
        else:
            w, h = abs(x2 - x1), abs(y2 - y1)
            if w < 3 or h < 3:
                return self.current() + [m.Toast(text="Too small: press Ctrl+Alt+P on two opposite corners.", kind="warn")]
            self.pins.steps[s.step.n] = Pin(box=(min(x1, x2), min(y1, y2), w, h))
        self._save_pins()
        self._scheme_cache.clear()
        return self.current() + [m.Toast(text=f"✓ Step {s.step.n} pinned. Ctrl+Alt+U removes it.")]

    def _save_pins(self) -> None:
        if self.pins_path is not None:
            self.pins.dump(self.pins_path)

    def _after(self, ev: Event) -> list[m._Msg]:
        if ev.kind == "noop":
            return []
        out = self.current()
        if ev.text:
            out.append(m.Toast(text=ev.text, kind="warn" if ev.kind == "skipped" else "ok",
                               ms=3000 if ev.kind in ("finished", "caught_up") else 2000))
        return out


JITTER_PX = 4    # a located box that moved this little is the same target


def _near(a: Optional[m.Box], b: Optional[m.Box]) -> bool:
    if a is None or b is None:
        return a is b
    return all(abs(p - q) <= JITTER_PX for p, q in ((a.x, b.x), (a.y, b.y), (a.w, b.w), (a.h, b.h)))
