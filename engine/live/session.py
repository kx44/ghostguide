"""The one state machine that owns "where you are" (live step 1, 8a, 8b): next, back, skip, jump,
hide / resume with catch-up. Overlay and hotkeys both go through here, so they agree.

No screen, no models: the step check is passed in as `checker` (live/verify.py).
Progress is saved after every change so a restart lands on the step you stopped at.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal, Optional

from engine.schema.tutorial import Step, Tutorial

Status = Literal["pending", "done", "skipped"]
CheckResult = Literal["done", "not_yet", "wrong", "unknown"]
Checker = Callable[[Step], "CheckResult | object"]     # a result string, or a verify.Verdict

# Catch-up never runs through more steps than this in one resume, so a checker that wrongly
# says "done" for everything can't race to the end.
MAX_CATCH_UP = 50


@dataclass
class Event:
    """What a session change means for the user, so the server can toast it."""
    kind: Literal["moved", "skipped", "finished", "hidden", "resumed", "caught_up", "noop"]
    text: str = ""
    steps: list[int] = field(default_factory=list)


class Session:
    def __init__(self, tutorial: Tutorial, save_path: Optional[Path] = None, checker: Optional[Checker] = None):
        self.tutorial = tutorial
        self.of = len(tutorial.steps)
        if self.of == 0:
            raise ValueError("tutorial has no steps")
        self.current = 1                       # 1-based; of + 1 once finished
        self.statuses: list[Status] = ["pending"] * self.of
        self.hidden = False
        self.save_path = save_path
        self.checker = checker
        self.history: list[tuple[str, int]] = []   # (op, step) for debugging and tests

    # ---------- reading ----------
    @property
    def finished(self) -> bool:
        return self.current > self.of

    @property
    def step(self) -> Optional[Step]:
        return None if self.finished else self.tutorial.step(self.current)

    def status(self, n: int) -> Status:
        return self.statuses[n - 1]

    # ---------- moving ----------
    def next(self) -> Event:
        """You say this step is done (Next button, hotkey), or a check said so."""
        if self.finished:
            return Event("noop")
        n = self.current
        self.statuses[n - 1] = "done"
        return self._advance(n, "next")

    def skip(self) -> Event:
        """Marks skipped, never done: skipping must not pretend the step was checked (8b)."""
        if self.finished:
            return Event("noop")
        n = self.current
        self.statuses[n - 1] = "skipped"
        ev = self._advance(n, "skip")
        if ev.kind == "finished":
            return ev
        return Event("skipped", f"Skipped step {n}. It stays marked in the step list.", [n])

    def back(self) -> Event:
        if self.current <= 1:
            return Event("noop")
        self.current -= 1
        self._log("back")
        return Event("moved", steps=[self.current])

    def jump(self, n: int) -> Event:
        if not 1 <= n <= self.of:
            raise ValueError(f"step {n} is outside 1..{self.of}")
        if n == self.current:
            return Event("noop")
        self.current = n
        self._log("jump")
        return Event("moved", steps=[n])

    def restart(self) -> None:
        self.current = 1
        self.statuses = ["pending"] * self.of
        self.hidden = False
        self._log("restart")

    def _advance(self, n: int, op: str) -> Event:
        self.current = n + 1
        self._log(op)
        if self.finished:
            skipped = [i + 1 for i, s in enumerate(self.statuses) if s == "skipped"]
            tail = f" ({len(skipped)} skipped)" if skipped else ""
            return Event("finished", f"✓ Tutorial complete{tail}", skipped)
        return Event("moved", steps=[self.current])

    # ---------- hide / resume (8a) ----------
    def hide(self) -> Event:
        if self.hidden:
            return Event("noop")
        self.hidden = True
        self._log("hide")
        return Event("hidden")

    def resume(self) -> Event:
        """Shows the overlay again and catches up: while the current step checks as done, mark it done
        and move on, stopping at the first step you haven't done (or the first one the checker can't tell)."""
        if not self.hidden:
            return Event("noop")
        self.hidden = False
        self._log("resume")
        caught = self.catch_up()
        if caught:
            if self.finished:
                return Event("finished", "✓ You finished it while hidden", caught)
            s = "s" if len(caught) > 1 else ""
            return Event("caught_up", f"✓ Caught up: step{s} {_ranges(caught)} done. You're on step {self.current}.", caught)
        return Event("resumed")

    def catch_up(self, checker: Optional[Checker] = None) -> list[int]:
        """Walk forward while the current step checks done. Stuck on a step the checker can't vouch for (no
        hint, or a fact that doesn't last such as "tab selected"), look further ahead: a later step whose
        done *lasts* (its code is in the file, its tab exists) means the steps before it were done too, as
        long as no lasting "not yet" lies in between. A "still typing" answer stops the scan outright.
        Also used by the live loop (live/verify.py), so early actions advance the same way as a resume."""
        checker = checker or self.checker
        if checker is None:
            return []
        done = self.scan(checker)
        self.apply_done(done, "catch_up")
        return done

    def apply_done(self, done: list[int], op: str = "auto") -> None:
        """Mark a scan's steps done and land on the one after them."""
        for n in done:
            self.statuses[n - 1] = "done"
        if done:
            self.current = done[-1] + 1
            self._log(op)

    def scan(self, checker: Checker) -> list[int]:
        """The steps catch_up would mark done, without changing anything (the engine runs this while hidden
        so Resume can answer at once from the result)."""
        done: list[int] = []
        cur = self.current
        while cur <= self.of and len(done) < MAX_CATCH_UP:
            v = _verdict(checker(self.tutorial.step(cur)))
            if v.result == "done":
                done.append(cur)
                cur += 1
                continue
            if _stops(v):
                break
            k = self._anchor(checker, cur, MAX_CATCH_UP - len(done))
            if k is None:
                break
            done.extend(range(cur, k + 1))
            cur = k + 1
        return done

    def _anchor(self, checker: Checker, cur: int, budget: int) -> Optional[int]:
        """Furthest step after `cur` whose done lasts, before any lasting not-yet."""
        best = None
        for n in range(cur + 1, min(self.of, cur + budget - 1) + 1):
            v = _verdict(checker(self.tutorial.step(n)))
            if _stops(v):
                break
            if v.result == "done" and v.lasting:
                best = n
        return best

    # ---------- persistence ----------
    def _log(self, op: str) -> None:
        self.history.append((op, self.current))
        self.save()

    def to_dict(self) -> dict:
        return {"tutorial": self.tutorial.meta.title, "of": self.of, "current": self.current,
                "statuses": self.statuses}

    def save(self) -> None:
        if self.save_path is None:
            return
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        self.save_path.write_text(json.dumps(self.to_dict(), indent=1), encoding="utf-8")

    def restore(self) -> bool:
        """Loads saved progress if it matches this tutorial (same title and step count)."""
        if self.save_path is None or not self.save_path.exists():
            return False
        try:
            data = json.loads(self.save_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if data.get("tutorial") != self.tutorial.meta.title or data.get("of") != self.of:
            return False
        statuses = data.get("statuses", [])
        if len(statuses) != self.of or any(s not in ("pending", "done", "skipped") for s in statuses):
            return False
        try:
            current = int(data.get("current", 1))
        except (TypeError, ValueError):
            return False
        self.statuses = list(statuses)
        self.current = max(1, min(current, self.of + 1))
        return True


@dataclass
class _Plain:
    """A plain string answer from a simple checker: "done" counts, nothing lasts."""
    result: str
    stage: str = "none"
    lasting: bool = False


def _verdict(v):
    return _Plain(v) if isinstance(v, str) else v


def _stops(v) -> bool:
    """A "not yet" that lasts, a wrong result, or "still typing": nothing past it counts."""
    return v.result == "wrong" or v.stage == "settle" or (v.result == "not_yet" and v.lasting)


def _ranges(ns: list[int]) -> str:
    """[3, 4, 5, 8] → '3–5, 8'."""
    out, start, prev = [], None, None
    for n in ns:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            out.append(f"{start}–{prev}" if prev != start else str(start))
            start = prev = n
    if start is not None:
        out.append(f"{start}–{prev}" if prev != start else str(start))
    return ", ".join(out)
