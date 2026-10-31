"""Glue between the session, the planner and the overlay, with no transport: one overlay message in →
the list of messages to send back. `engine/server.py` carries them over the WebSocket; tests and the
console mode call this directly.

Targets come from pinned boxes (locate/pinned.py, dev only), else from the locator (the resolver:
app map → UIA → vision → menu path); a pin always wins. Step checks come from the tracker (live/verify.py):
when the current step checks done it moves on by itself (smart Next), and while hidden it keeps checking so
Resume lands on the first step you haven't done.
"""
from __future__ import annotations

from typing import Callable, Optional, Protocol

from pydantic import ValidationError

from engine.live import source as source_view
from engine.live.execute import can_do, needs_confirm, plan as plan_ops, say_done
from engine.live.locate.pinned import Pin, Pins
from engine.live.plan import Planner
from engine.live.session import Event, Session
from engine.live.startcheck import holds_back
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
                 pins_path=None, locator: Optional[Locator] = None, tracker=None,
                 folder_fn: Optional[Callable[[], object]] = None, inputs=None, executor=None,
                 start_items: Optional[Callable[[], list[dict]]] = None):
        self.session = session
        self._acted: set[int] = set()            # steps Do it for me acted on
        self.executor = executor                # live/execute.Executor: Do it for me; None = not offered
        self._armed: Optional[int] = None        # the step whose Do it for me is waiting for its second press
        # The start check: only for a tutorial that hasn't begun. start_items() reads the real screen.
        self.start_items = start_items
        self.start_open = start_items is not None and session.current == 1 and session.statuses[0] == "pending"
        self._start_said: Optional[list[dict]] = None
        self.inputs = inputs                     # live/inputs.Recent: recent clicks (acted_on, card placement)
        self._drawn: dict[int, list[m.Box]] = {} # every box a step's guide was drawn at
        # Checks steps (live/verify.py Tracker). Slow like the locator, so the server runs check_round()
        # outside its lock and apply_checked() inside it.
        self.tracker = tracker
        self.folder_fn = folder_fn               # finds the working folder for `file` checks once the app is up
        self._hidden_scan: list[int] = []
        # Finds targets live. Slow (a UIA walk), so it never runs inside handle(): the server calls
        # locate_current() outside its lock and apply_located() with the result, so buttons answer at once.
        self.locator = locator
        self._located: dict[int, tuple[Optional[m.Box], Optional[m.Line]]] = {}
        self._located_extra: dict[int, dict] = {}   # e.g. editor clip + backing colour for ghost text
        self.pins_path = pins_path               # where Ctrl+Alt+P pins are saved; None = keep in memory
        self._corner: Optional[tuple[int, int]] = None   # first Ctrl+Alt+P of a pair
        self.planner = Planner(session.tutorial)
        self.sources = source_view.Sources(session.tutorial)
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
        if self.start_open and not s.hidden:
            items = self._start_read()
            if holds_back(items):
                self._start_said = items
                self.last_guide = None
                return [self.state(), m.Clear(reason="start"),
                        m.StartCheck(tutorial=s.tutorial.meta.title, items=[m.StartItem(**i) for i in items])]
            self.start_open = False
        if not s.finished and not s.hidden:
            step = s.step
            assert step is not None
            box, line = self.target(step.n)
            self.scheme = self._scheme(box, step.n)
            guide = self.planner.plan(step, box, line, self.displays, self.scheme)
            located = self._located_extra.get(step.n, {}) if step.n not in self.pins.steps else {}
            if guide.style in ("code_card", "ghost_text"):
                guide.extra.update(located)
            from engine.live.plan import avoid_areas
            avoid = avoid_areas(step, box, guide.extra if guide.style in ("code_card", "path_chips") else located)
            if avoid:
                guide.extra["avoid"] = avoid
            if located.get("route") and guide.card is not None:
                from engine.live.locate.menu import describe
                guide.card.detail = describe(located["route"])      # not on screen: say how to get there
                guide.card.compact = False
                guide.extra["route"] = located["route"]
                if located["route"].get("path"):
                    guide.extra.update(path=located["route"]["path"], path_done=0)
            if "path_done" in located:
                guide.extra["path_done"] = located["path_done"]
            if located.get("path"):
                guide.extra["path"] = located["path"]
                if guide.card is not None:
                    guide.card.detail = "Route: " + " › ".join(located["path"])
            if located.get("click_at"):
                guide.extra["click_at"] = list(located["click_at"])
            if located.get("shortcut"):
                guide.extra["shortcut"] = located["shortcut"]
            if guide.card is not None and self.executor is not None and can_do(step, self._act_box(step.n, box)):
                at = 1 if "show_me" in guide.card.actions else 0
                guide.card.actions.insert(at, "do_it")
            if guide.card is not None:
                guide.card.source = source_view.label(s.tutorial, step)
            if guide.card is not None and box is None and step.action not in NO_PIN_NEEDED and not located.get("route"):
                first = "start point" if step.action in LINE_ACTIONS else "top-left corner"
                second = "end point" if step.action in LINE_ACTIONS else "bottom-right corner"
                if self.locator is None:
                    guide.card.dev_hint = (f"Not pinned yet: Hover the {first} of {step.target.label} and press "
                                           f"Ctrl+Alt+P, then the {second} and Ctrl+Alt+P again." if self._corner is None
                                           else f"Now hover the {second} and press Ctrl+Alt+P.")
                elif self._corner is not None:
                    guide.card.dev_hint = f"Now hover the {second} and press Ctrl+Alt+P."
                elif step.n in self._located:
                    guide.card.dev_hint = f"Not found ({self.locator.last_how}). You can still do it by hand; Next moves on."
                else:
                    guide.card.dev_hint = "Looking for it…"
        if guide is not None and guide.box is not None:
            seen = self._drawn.setdefault(guide.step.n, [])
            if guide.box not in seen:
                seen.append(guide.box)
        out.append(self.state())
        if guide is None:
            out.append(m.Clear(reason="finished" if s.finished else "hidden"))
        else:
            out.append(guide)
        self.last_guide = guide
        return out

    # ---------- the start check ----------
    def _start_read(self) -> list[dict]:
        try:
            return self.start_items()
        except Exception:      # reading windows must never stop the tutorial from starting
            return []

    def start_round(self) -> list[m._Msg]:
        """While the start check is up: redraw when a tick changed, and go to step 1 once nothing holds it back."""
        if not self.start_open or self.session.hidden:
            return []
        items = self._start_read()
        if items == self._start_said and holds_back(items):
            return []
        was_up = self._start_said is not None
        out = self.current()
        if was_up and not self.start_open:
            out.append(m.Toast(text="✓ Ready. Here we go.", ms=1600))
        return out

    # ---------- Do it for me ----------
    def _act_box(self, n: int, box: Optional[m.Box]) -> Optional[m.Box]:
        """The box Do it for me may click: not the outline on a route's hop, which isn't the control."""
        return None if self._located_extra.get(n, {}).get("route") else box

    def _do_it(self) -> list[m._Msg]:
        s = self.session
        if self.executor is None:
            return [m.Toast(text="Do it for me isn't available for this app.", kind="warn")]
        if s.finished or s.hidden or s.step is None:
            return []
        step = s.step
        box = self._act_box(step.n, self.target(step.n)[0])
        if not can_do(step, box):
            return [m.Toast(text="There's nothing sure to act on for this step, so it's yours.", kind="warn")]
        stage = getattr(self.locator, "last_stage", "")
        if needs_confirm(step, stage, box) and step.n not in self.pins.steps and self._armed != step.n:
            self._armed = step.n
            return [m.Toast(text="Found by sight, not by name. Check the outline, then press Do it for me again.", ms=5000)]
        self._armed = None
        why = self.executor.run(plan_ops(step, box))
        if why:
            return [m.Toast(text=why, kind="warn", ms=4000)]
        if self.tracker is not None:     # we just acted on this step's target: a hint already true now counts
            self._acted.add(step.n)
        return [m.Toast(text=say_done(step), ms=2000)]

    def locate_current(self) -> Optional[tuple]:
        """Ask the locator about the current step: (step, box, line, extra), or None when there's nothing to ask.
        Reads the session but changes nothing, so the server runs it outside its lock."""
        s = self.session
        if self.start_open or self.locator is None or s.finished or s.hidden or s.step is None or s.step.n in self.pins.steps:
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

    # ---------- step checks (smart Next, tracking while hidden) ----------
    def check_round(self) -> Optional[tuple]:
        """Run the check ladder on the current step and the next few: (current step, hidden, steps done).
        Reads the session but changes nothing, so the server runs it outside its lock."""
        s, t = self.session, self.tracker
        if t is None or s.finished or self.start_open:
            return None
        if t.folder is None and self.folder_fn is not None:
            try:
                t.folder = self.folder_fn()
            except Exception:
                pass
        seed = None
        loc = self.locator
        if loc is not None and getattr(loc, "last_els", None) and _fresh(getattr(loc, "last_t", 0.0)):
            seed = loc.last_els
        snap = t.snapshot(seed)
        t.verdicts(s, snap)
        done = s.scan(t.checker(snap))
        return s.current, s.hidden, done

    def apply_checked(self, r) -> list[m._Msg]:
        """Act on a check_round() result: while showing, mark the steps done and move on; while hidden,
        remember them for Resume. Steps you already passed (Back, Jump) never auto-advance: only a step
        still pending does, so going back to look at one isn't undone a second later."""
        if r is None:
            return []
        cur, hidden, done = r
        s = self.session
        if s.current != cur or s.finished:
            return []          # the user moved meanwhile
        if s.hidden:
            self._hidden_scan = done if hidden else []
            return []
        if hidden or not done or s.status(cur) != "pending":
            return []
        had_target = self.last_guide is not None and self.last_guide.box is not None
        s.apply_done(done)
        learn = getattr(self.locator, "learn", None)
        for n in done:                     # checked done: stable controls are remembered for next time
            boxes = self._drawn.get(n)
            if learn is not None and boxes and n not in self.pins.steps:
                try:
                    learn(s.tutorial.step(n), boxes[-1])
                except Exception:
                    pass
        self._step_changed()
        out = ([m.Mark(result="ok")] if had_target else []) + self.current()
        text = ("✓ You finished it" if s.finished else
                f"✓ Step {done[0]} done" if len(done) == 1 else f"✓ Steps {done[0]}–{done[-1]} done")
        out.append(m.Toast(text=text, kind="ok", ms=1600))
        return out

    def acted_on(self, n: int, since: float, pad: int = 6) -> bool:
        """Did you click inside one of step n's drawn targets since `since`? (A click is never proof on its own:
        the tracker only uses this next to a hint that holds.)"""
        if n in self._acted:
            return True
        if self.inputs is None:
            return False
        boxes = self._drawn.get(n, [])
        return any(e.t >= since and any(b.x - pad <= e.x <= b.x + b.w + pad and b.y - pad <= e.y <= b.y + b.h + pad
                                        for b in boxes) for e in self.inputs.clicks(within_s=600))

    def _step_changed(self) -> None:
        self._armed = None
        if self.session.finished:
            return
        if self.tracker is not None:
            self.tracker.forget(self.session.current)
        forget = getattr(self.locator, "forget", None)
        if forget is not None:
            self._acted.discard(self.session.current)
            forget(self.session.current)

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
            return [sm] if sm else [m.Toast(text="This step has no target on screen, so there's nothing to show.", kind="warn")]
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
            return self._do_it()
        if t in ("source", "source_file"):
            return self._source(msg)
        if t == "toggle_scheme":
            return self._toggle_scheme()
        if t == "start_ok":
            self.start_open = False
            return self.current()
        if self.start_open and t in ("next", "skip", "back", "jump"):      # moving at all means you're past the checklist
            self.start_open = False
            if t == "next":
                return self.current()
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
            self._hidden_scan = []
            return self._after(s.hide())
        if t == "resume":
            # Catch up from what the tracker saw while hidden (it kept checking), so this answers at once.
            scan = list(self._hidden_scan)
            s.checker = (lambda step: "done" if step.n in scan else "unknown") if scan else None
            ev = s.resume()
            s.checker = None
            return self._after(ev)
        return []

    def _toggle_scheme(self) -> list[m._Msg]:
        """Ctrl+Alt+D: the other colours from now on; again: back to matching the app behind each target."""
        if self.scheme_override:
            self.scheme_override = None
            text = "Colours: automatic, matching the app."
        else:
            self.scheme_override = "light" if self.scheme == "dark" else "dark"
            text = f"Colours: {self.scheme_override}. Ctrl+Alt+D goes back to automatic."
        self._scheme_cache.clear()
        return self.current() + [m.Toast(text=text, ms=2500)]

    def _source(self, msg) -> list[m._Msg]:
        """The current step's source; the last step's once the tutorial has finished."""
        s = self.session
        step = s.step or s.tutorial.steps[-1]
        if msg.type == "source_file":
            return [self.sources.choose(msg.path, step, s.of)]
        return [self.sources.view(step, s.of, msg.follow)]

    def source_fetched(self) -> list[m._Msg]:
        """After the server's try at the page: the words, or why not. A step moved on meanwhile opens its own section."""
        s = self.session
        return [self.sources.view(s.step or s.tutorial.steps[-1], s.of, follow=True)]

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
        self._step_changed()
        out = self.current()
        if ev.text:
            out.append(m.Toast(text=ev.text, kind="warn" if ev.kind == "skipped" else "ok",
                               ms=3000 if ev.kind in ("finished", "caught_up") else 2000))
        return out


JITTER_PX = 4    # a located box that moved this little is the same target
DUMP_FRESH_S = 0.5   # a locator dump younger than this is reused by the step check


def _fresh(t: float) -> bool:
    import time
    return time.monotonic() - t <= DUMP_FRESH_S


def _near(a: Optional[m.Box], b: Optional[m.Box]) -> bool:
    if a is None or b is None:
        return a is b
    return all(abs(p - q) <= JITTER_PX for p, q in ((a.x, b.x), (a.y, b.y), (a.w, b.w), (a.h, b.h)))
