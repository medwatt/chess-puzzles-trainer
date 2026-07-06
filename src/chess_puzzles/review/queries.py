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


def due_reviews(conn: sqlite3.Connection, *, now: datetime | None = None) -> list[DueReview]:
    """Puzzles due for review at ``now``, most overdue first."""
    now = now or datetime.now(UTC)
    rows = conn.execute(
        "SELECT puzzle_id, at, grade, duration_ms, database_id, database_path"
        " FROM attempt ORDER BY puzzle_id, at, id"
    ).fetchall()
    due: list[DueReview] = []
    for puzzle_id, group in groupby(rows, key=lambda row: row["puzzle_id"]):
        history: list[Rep] = []
        database_id = database_path = ""
        for row in group:
            history.append(Rep(_parse_at(row["at"]), row["grade"], row["duration_ms"]))
            if row["database_path"]:
                database_id, database_path = row["database_id"], row["database_path"]
        when = next_due(history)
        if when is not None and when <= now:
            due.append(DueReview(puzzle_id, when, database_id, database_path))
    due.sort(key=lambda review: review.due)
    return due


def _parse_at(at: str) -> datetime:
    when = datetime.fromisoformat(at)
    # Attempts are stored with a UTC "Z" suffix (store/clock.now_iso), but be
    # tolerant of a naive timestamp from a hand-edited or ancient row.
    return when if when.tzinfo is not None else when.replace(tzinfo=UTC)
