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

# The interval ladder. A puzzle enters on its first attempt -- at the top rung
# if that attempt was a fast flawless solve, at the bottom otherwise -- climbs
# one rung per clean solve (two for a fast flawless one), repeats its rung on
# "hard", resets on "again", and graduates out past the top rung.
#
# Nothing is dismissed on a single attempt: one fast solve is weak evidence
# that a pattern is installed (the puzzle may simply have been easy), and a
# puzzle that entered the ladder has to be solved cleanly three times before
# it is dropped. Entering at the top rung applies that same bar without
# insulting the solver by asking again tomorrow.
INTERVALS: tuple[timedelta, ...] = (timedelta(days=1), timedelta(days=3), timedelta(days=10))

# Solve-speed budget, scaled by how much there was to solve: a mate in one and
# a six-move combination cannot share a stopwatch. Calibrated so the threshold
# sits near the upper quartile of clean solves at every length -- "slower than
# you usually are at this length" rather than a fixed number of seconds.
SLOW_BASE_MS = 12_000
SLOW_PER_EXTRA_DECISION_MS = 16_000
# Attempts recorded before the solution length was stored keep the flat
# threshold they were originally graded by, so history does not shift.
SLOW_MS = 30_000


def slow_threshold_ms(solution_plies: int | None) -> int:
    """How long a clean solve may take before it counts as not yet automatic.

    The solver only chooses on their own turns, so a line of N plies asks
    about half that many questions.
    """
    if solution_plies is None:
        return SLOW_MS
    decisions = max((solution_plies + 1) // 2, 1)
    return SLOW_BASE_MS + SLOW_PER_EXTRA_DECISION_MS * (decisions - 1)


@dataclass(frozen=True, slots=True)
class Rep:
    """One recorded attempt, as the scheduler sees it."""

    at: datetime
    grade: str  # "again" | "hard" | "good" | "easy" (attempt.grade)
    duration_ms: int | None = None
    solution_plies: int | None = None


def effective_grade(rep: Rep) -> str:
    """The recorded grade, demoted one step when the solve was slow."""
    if rep.duration_ms is not None and rep.duration_ms > slow_threshold_ms(rep.solution_plies):
        return {"easy": "good", "good": "hard"}.get(rep.grade, rep.grade)
    return rep.grade


def next_due(history: Sequence[Rep]) -> datetime | None:
    """The next review time, or None once the puzzle has graduated.

    ``history`` must be one puzzle's attempts in chronological order. A
    graduated puzzle re-enters if a later attempt fails it.
    """
    rung: int | None = None
    for rep in history:
        grade = effective_grade(rep)
        if rung is None:
            # A fast flawless first solve still gets one long-delayed check.
            rung = len(INTERVALS) - 1 if grade == "easy" else 0
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
