"""The arena session rating, derived from the attempt log.

Follows the scheduler's pattern (review/scheduler.py): pure policy over the
append-only attempt log, no stored rating anywhere. The session rating is a
fold seeded by the arena deck's start_rating; recomputing it is one indexed
query plus arithmetic, so it can never go stale and the formula can change
retroactively.

Policy elo-v1: only the FIRST RATED attempt per puzzle in the arena is rated
(later attempts are review re-solves, which must not move the session rating
retroactively). A win is a clean solve -- outcome 'solved' with zero mistakes
and zero aids; everything else, including giving up, is a loss. Attempts
without a stored puzzle_rating (legacy rows, unrated content) are completely
ignored: they neither change the rating nor consume that puzzle's first-rated-
attempt slot.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass

RATING_POLICY_ELO_V1 = "elo-v1"

# K schedule: converge fast from the user-chosen start, then settle.
_K_EARLY = 40.0
_K_LATE = 20.0
_EARLY_ATTEMPTS = 20


@dataclass(frozen=True, slots=True)
class RatedAttempt:
    """One attempt row, as the rating fold sees it (in attempt.id order)."""

    puzzle_id: str
    puzzle_rating: int | None
    outcome: str
    mistakes: int
    aids: int


def is_win(attempt: RatedAttempt) -> bool:
    """Whether a rated attempt counts as a win.

    The Python twin of ``reports.queries.CLEAN_SOLVE``: same three conditions,
    expressed here over a dataclass rather than in SQL because the rating fold
    walks attempts in order. Change one and change the other -- the per-deck
    table drifting from this rule is exactly what made an assisted solve show
    as clean in one place and not the other."""
    return attempt.outcome == "solved" and attempt.mistakes == 0 and attempt.aids == 0


def elo_v1_rating(start_rating: float, attempts: Iterable[RatedAttempt]) -> float:
    """Fold the session's attempts into its current rating.

    ``attempts`` must be one arena's attempts in attempt.id order; the
    first-rated-attempt-per-puzzle filter happens here so callers pass raw
    history. A null-rated row is outside the policy, not a rated result.
    """
    rating = float(start_rating)
    seen: set[str] = set()
    rated_count = 0
    for attempt in attempts:
        if attempt.puzzle_rating is None:
            continue
        if attempt.puzzle_id in seen:
            continue
        seen.add(attempt.puzzle_id)
        expected = 1.0 / (1.0 + 10.0 ** ((attempt.puzzle_rating - rating) / 400.0))
        score = 1.0 if is_win(attempt) else 0.0
        k = _K_EARLY if rated_count < _EARLY_ATTEMPTS else _K_LATE
        rating += k * (score - expected)
        rated_count += 1
    return rating


def session_attempts(conn: sqlite3.Connection, database_id: str) -> list[RatedAttempt]:
    """One arena's attempt history in id order (ties in `at` are possible)."""
    rows = conn.execute(
        "SELECT puzzle_id, puzzle_rating, outcome, mistakes, aids"
        " FROM attempt WHERE database_id = ? ORDER BY id",
        (database_id,),
    )
    return [
        RatedAttempt(
            row["puzzle_id"], row["puzzle_rating"], row["outcome"], row["mistakes"], row["aids"]
        )
        for row in rows
    ]


def session_rating(conn: sqlite3.Connection, database_id: str, start_rating: float) -> float:
    return elo_v1_rating(start_rating, session_attempts(conn, database_id))


def first_attempt_losses(conn: sqlite3.Connection, database_id: str) -> list[str]:
    """Puzzle ids whose first RATED attempt in this arena was a loss.

    This is the session's historical mistake list -- distinct from the due
    review queue, which reflects what currently needs re-training. A later
    clean review re-solve does not remove a puzzle from history, and a failed
    review after a clean first solve does not add one."""
    losses: list[str] = []
    seen: set[str] = set()
    for attempt in session_attempts(conn, database_id):
        if attempt.puzzle_rating is None:
            continue
        if attempt.puzzle_id in seen:
            continue
        seen.add(attempt.puzzle_id)
        if not is_win(attempt):
            losses.append(attempt.puzzle_id)
    return losses
