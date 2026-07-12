from __future__ import annotations

import sqlite3
from collections.abc import Iterable

from chess_puzzles.reports.model import AttemptSummary, DeckSummary


def attempt_summary(
    conn: sqlite3.Connection,
    *,
    since: str | None = None,
    puzzle_ids: Iterable[str] | None = None,
) -> AttemptSummary:
    clauses: list[str] = []
    params: list[str] = []
    if since is not None:
        clauses.append("at >= ?")
        params.append(since)
    if puzzle_ids is not None:
        ids = tuple(puzzle_ids)
        if not ids:
            return AttemptSummary(attempted=0, solved=0, gave_up=0, total_ms=0)
        clauses.append(f"puzzle_id IN ({','.join('?' for _ in ids)})")
        params.extend(ids)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    solved = "outcome = 'solved' AND mistakes = 0"
    row = conn.execute(
        "SELECT"
        " COUNT(*) AS attempted,"
        f" COALESCE(SUM(CASE WHEN {solved} THEN 1 ELSE 0 END), 0) AS solved,"
        " COALESCE(SUM(CASE WHEN outcome = 'gave_up' THEN 1 ELSE 0 END), 0) AS gave_up,"
        " COALESCE(SUM(duration_ms), 0) AS total_ms"
        f" FROM attempt{where}",
        params,
    ).fetchone()
    return AttemptSummary(
        attempted=int(row[0]),
        solved=int(row[1]),
        gave_up=int(row[2]),
        total_ms=int(row[3]),
    )


def deck_summaries(conn: sqlite3.Connection) -> list[DeckSummary]:
    rows = conn.execute(
        "SELECT a.database_id, COALESCE(c.name, '') AS name, MAX(a.database_path) AS database_path, COUNT(*) AS attempted,"
        " SUM(CASE WHEN outcome = 'solved' AND mistakes = 0 THEN 1 ELSE 0 END) AS clean_solves,"
        " SUM(mistakes) AS mistakes, SUM(aids) AS aids, COALESCE(SUM(duration_ms), 0) AS total_ms"
        " FROM attempt a LEFT JOIN library_course c ON c.database_id=a.database_id"
        " GROUP BY a.database_id ORDER BY MAX(a.at) DESC, a.database_id"
    )
    return [
        DeckSummary(
            row["database_id"], row["name"], row["database_path"], row["attempted"],
            row["clean_solves"], row["mistakes"], row["aids"], row["total_ms"]
        )
        for row in rows
    ]
