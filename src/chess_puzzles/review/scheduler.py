"""When a puzzle is next due for review, derived from its attempt history.

Tuned for pattern training, not fact retention: a short, aggressive interval
ladder that flushes a puzzle after a few clean solves (the goal is closing the
gap, not lifetime recall), plus a speed demotion so a slow-but-correct solve
counts as "not yet automatic" rather than success -- recognition speed, not
correctness, is what graduates a puzzle.

Pure policy over the append-only attempt log: no scheduling state is stored
anywhere, so changing this function reschedules every puzzle retroactively
with no migration.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

# The interval ladder. A puzzle enters at rung 0 on its first non-easy attempt,
# climbs one rung per clean solve (two for a fast flawless one), repeats its
# rung on "hard", resets on "again", and graduates out past the top rung.
INTERVALS: tuple[timedelta, ...] = (timedelta(days=1), timedelta(days=3), timedelta(days=10))

# Solves slower than this demote one grade step (easy -> good -> hard).
# ponytail: flat threshold; scale by solution length if it proves unfair.
SLOW_MS = 30_000


@dataclass(frozen=True, slots=True)
class Rep:
    """One recorded attempt, as the scheduler sees it."""

    at: datetime
    grade: str  # "again" | "hard" | "good" | "easy" (attempt.grade)
    duration_ms: int | None = None


def effective_grade(rep: Rep) -> str:
    """The recorded grade, demoted one step when the solve was slow."""
    if rep.duration_ms is not None and rep.duration_ms > SLOW_MS:
        return {"easy": "good", "good": "hard"}.get(rep.grade, rep.grade)
    return rep.grade


def next_due(history: Sequence[Rep]) -> datetime | None:
    """The next review time, or None when the puzzle never entered or graduated.

    ``history`` must be one puzzle's attempts in chronological order. A puzzle
    whose every attempt is a fast flawless solve never enters review; a
    graduated puzzle re-enters if a later attempt fails it.
    """
    rung: int | None = None
    for rep in history:
        grade = effective_grade(rep)
        if rung is None:
            if grade == "easy":
                continue  # fast flawless solve: nothing to train here
            rung = 0
        elif grade == "again":
            rung = 0
        elif grade == "good":
            rung += 1
        elif grade == "easy":
            rung += 2
        # "hard" repeats the current rung
    if rung is None or rung >= len(INTERVALS):
        return None
    return history[-1].at + INTERVALS[rung]
