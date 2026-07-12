"""Due-review queries over the attempt log.

Follows the connection-taking pattern of ``reports/queries.py``: SQL fetches
the raw rows, Python applies the scheduling policy. Due-ness is recomputed
from the full history on every call -- there is no stored schedule to go stale.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import groupby

from chess_puzzles.review.scheduler import Rep, next_due


@dataclass(frozen=True, slots=True)
class DueReview:
    puzzle_id: str
    due: datetime
    # Latest non-empty locator across the puzzle's attempts; '' when every
    # attempt predates the locator columns (resolvable only from an open deck).
    database_id: str
    database_path: str


def due_reviews(
    conn: sqlite3.Connection,
    *,
    now: datetime | None = None,
    database_id: str | None = None,
) -> list[DueReview]:
    """Puzzles due for review at ``now``, most overdue first.

    ``database_id`` scopes the queue to one deck (reviewing an opening course
    should not mix in tactics from elsewhere). Items with an empty locator --
    attempts predating the locator columns -- are kept in a scoped queue too:
    they are only ever resolvable against the currently open deck, which is
    exactly the deck being scoped to.
    """
    now = now or datetime.now(UTC)
    rows = conn.execute(
        "SELECT puzzle_id, at, grade, duration_ms, database_id, database_path"
        " FROM attempt ORDER BY puzzle_id, at, id"
    ).fetchall()
    due: list[DueReview] = []
    for puzzle_id, group in groupby(rows, key=lambda row: row["puzzle_id"]):
        history: list[Rep] = []
        locator_id = locator_path = ""
        for row in group:
            history.append(Rep(_parse_at(row["at"]), row["grade"], row["duration_ms"]))
            if row["database_path"]:
                locator_id, locator_path = row["database_id"], row["database_path"]
        when = next_due(history)
        if when is not None and when <= now:
            due.append(DueReview(puzzle_id, when, locator_id, locator_path))
    if database_id is not None:
        due = [review for review in due if review.database_id in ("", database_id)]
    due.sort(key=lambda review: review.due)
    return due


def _parse_at(at: str) -> datetime:
    when = datetime.fromisoformat(at)
    # Attempts are stored with a UTC "Z" suffix (store/clock.now_iso), but be
    # tolerant of a naive timestamp from a hand-edited or ancient row.
    return when if when.tzinfo is not None else when.replace(tzinfo=UTC)
