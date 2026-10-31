"""Did the step work? The check ladder (live step 9), cheapest first, stopping at the first sure answer:

  9a rule      the step's `verify` hint against UI Automation and the files on disk          free, exact
  9b diff      the step's region now vs when the step began: unchanged = not yet             free
  9c Glimmer   screenshot + the `check` sentence (Modal)                                     wired, off
  9d Spark     same question to Spark Contributor                                            wired, off

A verdict is done / not_yet / wrong / unknown, plus whether the answer *lasts*. Code in a file, a file on disk
or an open tab stays true after later steps; "this tab is selected" or "the filename box is open" doesn't.
Catch-up (session.catch_up) only lets lasting results stand in for the steps before them, so a tab that
happens to be selected can't skip work you never did. A lasting "not yet" stops the scan; a passing one
says nothing.

Two guards keep auto-advance honest:
- trust: a rule that was already true the first time it was looked at (a Live Server tab left open from
  yesterday) proves nothing, so it counts only once it has been seen false in this run (`Ladder.seen_false`).
- settle: a typing step counts as done only once you've stopped typing for a moment, so the card doesn't
  change under you mid-line (`Tracker`, from the input watcher).
Never blocks anything: a wrong or early action just means the check doesn't say done yet; Next always works.

The rule check is pure over a `Snapshot` (dumped UIA elements + a file reader), so it's unit-tested off Windows.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal, Optional

from engine.schema.tutorial import FileCheck, Step, UiaCheck

Result = Literal["done", "not_yet", "wrong", "unknown"]

TYPE_SETTLE_S = 1.2      # no keys or clicks for this long before a typing step counts as done
WAIT_SETTLE_S = 1.5      # a wait step's window must stay still this long
WAIT_MIN_S = 1.0         # …and the wait card must have been up at least this long
LOOK_AHEAD = 3           # steps after the current one that each tick also looks at (keeps `seen_false` fresh)
BASELINE_FRESH_S = 4.0   # a picture this recent still shows the app as a new step found it
MODEL_IDLE_S = 1.0       # no keys or clicks for this long before a model looks
MODEL_GAP_S = 4.0        # at least this long between two looks at one step
MODEL_MAX_ASKS = 6       # …and this many in all; after that Next is the way on


@dataclass
class Verdict:
    result: Result
    stage: str = "none"          # rule | diff | glimmer | spark | settle | none
    lasting: bool = False        # the answer stays true after later steps (see the module doc)
    why: str = ""
    untrusted: bool = False      # the hint holds, but it already did when the tutorial started

    @property
    def done(self) -> bool:
        return self.result == "done"


UNKNOWN = Verdict("unknown")


# ---------- what a check reads ------------------------------------------------------------------
@dataclass
class Snapshot:
    """One round of facts: UIA elements per window (dumped on first use), and files under the folder."""
    app_window: str                                     # e.g. "youtube-clone - Visual Studio Code"
    dump: Callable[[str], list[dict]]                   # window title part → its elements
    folder: Optional[Path] = None
    t: float = field(default_factory=time.monotonic)
    _els: dict[str, list[dict]] = field(default_factory=dict)

    def elements(self, window: Optional[str]) -> list[dict]:
        key = self.app_window if not window or window.casefold() in self.app_window.casefold() else window
        if key not in self._els:
            try:
                self._els[key] = self.dump(key)
            except Exception:
                self._els[key] = []
        return self._els[key]

    def seed(self, window: str, els: list[dict]) -> None:
        """Reuse a dump the locator just made, instead of walking the window twice."""
        self._els[window] = els

    def read(self, rel: str) -> Optional[str]:
        if self.folder is None:
            return None
        try:
            return (self.folder / rel).read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
        except OSError:
            return None


def _norm(s: Optional[str]) -> str:
    return " ".join((s or "").replace("…", "...").split()).casefold()


def _squash(s: str) -> str:
    return re.sub(r"\s+", "", s)


def step_file(step: Step) -> Optional[str]:
    """The file a step types into, from `where` ("index.html, inside <body>" → index.html)."""
    w = (step.target.where or "").split(",")[0].strip()
    return w if re.fullmatch(r"[\w.-]+\.\w+", w) else None


def typed_lines_present(value: str, text: str) -> bool:
    """Every non-blank line of a multi-line value appears in the text, spaces ignored. Editors add closing
    tags and indent on their own, so the whole block rarely matches byte for byte, but each line still shows."""
    flat = _squash(text)
    return all(_squash(ln) in flat for ln in value.split("\n") if ln.strip())


def _uia_hit(c: UiaCheck, el: dict) -> bool:
    if c.type and el.get("type") != c.type:
        return False
    if c.name is not None and _norm(el.get("name")) != _norm(c.name):
        return False
    if c.name_contains and _norm(c.name_contains) not in _norm(el.get("name")):
        return False
    if c.value is not None and el.get("value") != c.value:
        return False
    if c.value_contains and c.value_contains not in (el.get("value") or ""):
        return False
    if c.selected is not None and el.get("selected") is not c.selected:
        return False
    return True


def lasting(c: UiaCheck) -> bool:
    """Does this fact stay true after later steps? Code typed into an editor and an open tab do; a selected
    tab, an open box or an address bar is just how the screen is right now."""
    if c.selected is not None or not c.exists:
        return False
    if c.type == "Edit" and (c.value_contains or c.value):
        return c.name is None or "." in (c.name or "")      # an editor (named after its file), not a field
    if c.type in ("TabItem", "TreeItem"):      # a tab stays open, a feature stays in the tree
        return True
    return False


# ---------- 9a: rule check ---------------------------------------------------------------------
def rule_check(step: Step, snap: Snapshot) -> Verdict:
    """The step's `verify` hints. All must hold for done. Unknown when there's no hint, or what it needs
    isn't readable right now (another file is in the editor and the disk copy doesn't have it yet)."""
    if step.verify is None:
        return Verdict("unknown", "rule", why="no verify hint")
    verdicts = [_file_verdict(fc, snap) for fc in step.verify.file_checks()]
    verdicts += [_uia_verdict(step, uc, snap) for uc in step.verify.uia_checks()]
    if step.action == "type" and verdicts and all(v.done for v in verdicts):
        verdicts.append(_typed_verdict(step, snap))
    if any(v.result == "unknown" for v in verdicts):
        why = next(v.why for v in verdicts if v.result == "unknown")
        return Verdict("unknown", "rule", why=why)
    if all(v.done for v in verdicts):
        return Verdict("done", "rule", lasting=all(v.lasting for v in verdicts), why="verify hint holds")
    bad = [v for v in verdicts if not v.done]
    # A failed fact that doesn't last is a weak "not yet": the tab may simply have been switched away since,
    # so catch-up looks past it (lasting=False) while a lasting one stops it.
    return Verdict("not_yet", "rule", lasting=any(v.lasting for v in bad), why=bad[0].why)


def _file_verdict(fc: FileCheck, snap: Snapshot) -> Verdict:
    if snap.folder is None:
        return Verdict("unknown", why="working folder not known")
    text = snap.read(fc.path)
    exists = text is not None
    ok = exists == fc.exists
    if ok and exists:
        ok = (fc.contains is None or fc.contains in text) and (fc.not_contains is None or fc.not_contains not in text)
    return Verdict("done" if ok else "not_yet", lasting=True,
                   why="" if ok else f"{fc.path} on disk doesn't have it yet" if exists else f"no {fc.path} yet")


def _uia_verdict(step: Step, c: UiaCheck, snap: Snapshot) -> Verdict:
    els = snap.elements(c.window)
    if not els:
        return Verdict("unknown", why=f"can't read the {c.window or snap.app_window} window")
    last = lasting(c)
    fname = step_file(step)
    editor_check = c.type == "Edit" and c.name is None and c.name_contains is None and fname is not None
    if editor_check:
        # Only the editor showing this step's file counts: the Edit Monaco names after the file.
        eds = [e for e in els if e.get("type") == "Edit" and _norm(e.get("name")) == _norm(fname)]
        if not eds or all(e.get("value") is None for e in eds):
            disk = snap.read(fname)
            if disk is not None and c.value_contains and c.value_contains in disk:
                return Verdict("done", lasting=True, why=f"{fname} on disk has it")
            return Verdict("unknown", why=f"{fname} isn't the open editor")
        els = eds
    hit = any(_uia_hit(c, e) for e in els)
    ok = hit if c.exists else not hit
    return Verdict("done" if ok else "not_yet", lasting=last, why="" if ok else _describe(c))


def _typed_verdict(step: Step, snap: Snapshot) -> Verdict:
    """For multi-line typing: the hint names one key line; also require every line of the code, so a half
    typed block doesn't count."""
    value = str(step.params.get("value") or "")
    fname = step_file(step)
    if "\n" not in value.rstrip("\n") or fname is None:
        return Verdict("done", lasting=True)
    eds = [e for e in snap.elements(None) if e.get("type") == "Edit" and _norm(e.get("name")) == _norm(fname)
           and e.get("value") is not None]
    text = eds[0]["value"] if eds else snap.read(fname)
    if text is None:
        return Verdict("unknown", why=f"{fname} isn't readable")
    ok = typed_lines_present(value, text)
    return Verdict("done" if ok else "not_yet", lasting=True, why="" if ok else "not all of the code is there yet")


def _describe(c: UiaCheck) -> str:
    what = c.name or c.name_contains or c.type
    if c.value_contains:
        return f"no {c.type or 'element'} containing {c.value_contains!r}"
    if c.selected:
        return f"{what} isn't selected"
    return f"no {what}" if c.exists else f"{what} is still there"


# ---------- the ladder --------------------------------------------------------------------------
class Ladder:
    """Rule → diff → model checks for one step, with the trust guard. Model stages are plugged in as
    callables (models/glimmer.py) and are None while credits / Modal aren't set up."""

    def __init__(self, glimmer=None, spark=None):
        self.glimmer = glimmer           # (step, png) → Verdict
        self.spark = spark
        self.seen: set[int] = set()              # steps looked at at least once
        self.true_at_start: set[int] = set()     # …whose hint already held that first time
        self.seen_false: set[int] = set()        # …and have been seen false since

    def rule(self, step: Step, snap: Snapshot) -> Verdict:
        """The rule check with the trust guard: a hint that held the first time it was looked at (the
        tracker looks at every step when the tutorial starts) only counts once it has been seen false.
        Unreadable at first (the file didn't exist yet) isn't "true at the start"."""
        v = rule_check(step, snap)
        if step.n not in self.seen:
            self.seen.add(step.n)
            if v.done:
                self.true_at_start.add(step.n)
        if v.result == "not_yet":
            self.seen_false.add(step.n)
        if v.done and step.n in self.true_at_start and step.n not in self.seen_false:
            return Verdict("unknown", "rule", lasting=v.lasting, untrusted=True,
                           why="can't tell: it was already true when the tutorial started")
        return v

    def model(self, step: Step, png: Optional[bytes]) -> Verdict:
        for stage, fn in (("glimmer", self.glimmer), ("spark", self.spark)):
            if fn is None or png is None:
                continue
            try:
                v = fn(step, png)
            except Exception as e:
                v = Verdict("unknown", stage, why=f"{stage} failed: {e}")
            if v.result != "unknown":
                return v
        return Verdict("unknown", "none", why="no sure answer; press Next when it's done")


@dataclass
class _StepWatch:
    """Per-step memory for the diff stage: the region when the step began, and when it last changed."""
    shown_at: float
    baseline: object = None              # PIL image
    last: object = None
    last_change: float = 0.0
    asked: object = None                 # the picture the models last looked at
    asked_t: float = -1e9
    asks: int = 0
    answer: Optional[Verdict] = None     # …and what they said


class Tracker:
    """Runs the ladder each tick (and right after input) for the current step and a few after it. Owns the
    trust guard, the settle timers and the diff baselines. The Windows bits (dump, capture, input watcher)
    are passed in so tests can fake them."""

    def __init__(self, tutorial, app_window: str, folder: Optional[Path], dump: Callable[[str], list[dict]],
                 ladder: Optional[Ladder] = None, idle_s: Optional[Callable[[], float]] = None,
                 grab: Optional[Callable[[Step], object]] = None, clock: Callable[[], float] = time.monotonic,
                 acted: Optional[Callable[[int, float], bool]] = None):
        self.tutorial = tutorial
        self.app_window = app_window
        self.folder = folder
        self.dump = dump
        self.ladder = ladder or Ladder()
        self.idle_s = idle_s              # seconds since the last key / click (input watcher); None = always idle
        self.grab = grab                  # step → image of the region it changes (capture.py); None = no diff
        self.clock = clock
        # (step, since) -> did you click on that step's target since then? Lets a hint that was already true
        # at the start count once you've acted on the step (a Live Server tab left open from last time).
        self.acted = acted
        self.cache: dict[int, Verdict] = {}       # last verdict per step, for an instant catch-up on resume
        self._watch: dict[int, _StepWatch] = {}
        self.primed = False
        self.last_snapshot: Optional[Snapshot] = None
        self.last_img = None                      # the latest picture of the whole app
        self.last_img_t = -1e9
        self.close_up = None                      # (step, since, picture) → the part to show the models, or None
        self.model_w = 1280                       # the picture's width for the models
        self.diff_opts: dict = {}                 # capture.changed's width and share, for a picture of the whole app
        self.current_n: Optional[int] = None      # models only ever look at the step showing
        self.hidden = False                       # …and never while hidden (free checks only)

    def snapshot(self, seed: Optional[list[dict]] = None) -> Snapshot:
        snap = Snapshot(self.app_window, self.dump, self.folder, t=self.clock())
        if seed:
            snap.seed(self.app_window, seed)
        self.last_snapshot = snap
        return snap

    def prime(self, snap: Snapshot) -> None:
        """Look at every step once, so `seen_false` knows which facts were already true at the start."""
        if not snap.elements(None):
            return                        # app window not up yet: try again next tick
        for step in self.tutorial.steps:
            if step.verify is not None:
                self.cache[step.n] = self.ladder.rule(step, snap)
        self.primed = True

    def check(self, step: Step, snap: Snapshot) -> Verdict:
        """The full verdict for one step right now (rule, settle, wait, diff, models)."""
        now = self.clock()
        w = self._watch.setdefault(step.n, _StepWatch(shown_at=now))
        if step.action == "wait":
            v = self._wait(step, snap, w, now)
        else:
            v = self.ladder.rule(step, snap)
            if v.untrusted and self.acted is not None and self.acted(step.n, w.shown_at):
                v = Verdict("done", "rule", lasting=v.lasting, why="holds, and you clicked the target during this step")
            if v.result == "unknown" and step.verify is None:
                v = self._diff(step, w, now)
        if v.done and step.action == "type" and self.idle_s is not None and self.idle_s() < TYPE_SETTLE_S:
            v = Verdict("not_yet", "settle", why="still typing")
        self.cache[step.n] = v
        return v

    def _wait(self, step: Step, snap: Snapshot, w: _StepWatch, now: float) -> Verdict:
        """Wait steps: the hint (if any) holds and the window has stayed still for a moment."""
        if step.verify is not None:
            r = self.ladder.rule(step, snap)
            if r.result == "not_yet":
                return r
        if now - w.shown_at < WAIT_MIN_S:
            return Verdict("not_yet", "settle", why="just started")
        if self.grab is None:
            return Verdict("unknown", "diff", why="can't see the window")
        img = self.grab(step)
        if img is None:
            return Verdict("unknown", "diff", why="can't see the window")
        from engine.live.capture import changed
        if w.last is None or changed(w.last, img):
            w.last, w.last_change = img, now
            return Verdict("not_yet", "diff", why="still changing")
        if now - w.last_change < WAIT_SETTLE_S:
            return Verdict("not_yet", "diff", why="settling")
        return Verdict("done", "diff", why="the window has settled")

    def _diff(self, step: Step, w: _StepWatch, now: float) -> Verdict:
        """9b for steps without a hint: unchanged since the step began = not yet, no model call. Changed =
        the model stages (off without credits) or unknown."""
        if self.grab is None:
            return Verdict("unknown", "diff", why="no hint and no screen capture")
        if step.action == "look":
            return Verdict("not_yet", "diff", why="you say when")
        if self.current_n is not None and step.n != self.current_n:
            return Verdict("not_yet", "diff", why="not its turn")
        img = self.grab(step)
        if img is None:
            return Verdict("unknown", "diff", why="can't see the window")
        from engine.live.capture import changed, for_model
        previous, self.last_img = self.last_img, img
        if w.baseline is None:
            # Quick hands act before the first look at a step: the picture from just before it showed is the fairer start.
            w.baseline = previous if previous is not None and now - self.last_img_t < BASELINE_FRESH_S else img
            self.last_img_t = now
            if w.baseline is img:
                return Verdict("not_yet", "diff", why="baseline taken")
        self.last_img_t = now
        if not changed(w.baseline, img, **self.diff_opts):
            return Verdict("not_yet", "diff", why="nothing changed yet")
        if self.hidden or not (self.ladder.glimmer or self.ladder.spark):
            return Verdict("unknown", "diff", why="changed; no model to ask")
        return self._ask_model(step, w, now, img, for_model)

    def _ask_model(self, step: Step, w: _StepWatch, now: float, img, for_model) -> Verdict:
        """The window changed and no rule can tell, so look. Models are slow and cost money, and this runs every
        tick: ask only when you've paused, when the window has changed since the last answer, and not too often."""
        from engine.live.capture import changed
        idle = self.idle_s() if self.idle_s is not None else 1e9
        unchanged = w.asked is not None and not changed(w.asked, img, **self.diff_opts)
        if (idle < MODEL_IDLE_S or unchanged or now - w.asked_t < MODEL_GAP_S or w.asks >= MODEL_MAX_ASKS):
            return w.answer or Verdict("unknown", "diff", why="waiting to look")
        w.asked, w.asked_t = img, now
        w.asks += 1
        look = self.close_up(step, w.shown_at, img) if self.close_up is not None else None
        w.answer = self.ladder.model(step, for_model(img if look is None else look, self.model_w)[0])
        return w.answer

    def forget(self, n: int) -> None:
        """The step is showing again (Back, Jump, resume): start its timers and baseline over."""
        self._watch.pop(n, None)

    def verdicts(self, session, snap: Snapshot) -> dict[int, Verdict]:
        """Verdicts for the current step and the next LOOK_AHEAD (keeps the trust guard fresh)."""
        if not self.primed:
            self.prime(snap)
        self.current_n, self.hidden = session.current, session.hidden
        out = {}
        for n in range(session.current, min(session.of, session.current + LOOK_AHEAD) + 1):
            out[n] = self.check(session.tutorial.step(n), snap)
        return out

    def checker(self, snap: Snapshot) -> Callable[[Step], Verdict]:
        """A session checker for one round: steps already checked this round answer from the cache,
        others are checked now (catch-up can scan past the look-ahead)."""
        fresh: dict[int, Verdict] = {}

        def check(step: Step) -> Verdict:
            if step.n not in fresh:
                fresh[step.n] = self.check(step, snap)
            return fresh[step.n]
        return check

    def cached(self, step: Step) -> Verdict:
        return self.cache.get(step.n, UNKNOWN)
