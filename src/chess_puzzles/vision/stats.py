"""Persistent board-vision statistics queries over ``vision_attempt``.

Follows the connection-taking pattern of ``reports/queries.py``. The live HUD
in the window uses ``SessionStats``; this is for cross-session history.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VisionSummary:
    trials: int
    passed: int
    total_ms: int

    @property
    def accuracy_percent(self) -> float:
        return 100.0 * self.passed / self.trials if self.trials else 0.0

    @property
    def average_ms(self) -> int:
        return self.total_ms // self.trials if self.trials else 0


def vision_summary(
    conn: sqlite3.Connection,
    *,
    since: str | None = None,
    drill_id: str | None = None,
) -> VisionSummary:
    clauses: list[str] = []
    params: list[str] = []
    if since is not None:
        clauses.append("at >= ?")
        params.append(since)
    if drill_id is not None:
        clauses.append("drill_id = ?")
        params.append(drill_id)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    row = conn.execute(
        "SELECT"
        " COUNT(*) AS trials,"
        " COALESCE(SUM(passed), 0) AS passed,"
        " COALESCE(SUM(elapsed_ms), 0) AS total_ms"
        f" FROM vision_attempt{where}",
        params,
    ).fetchone()
    return VisionSummary(trials=int(row[0]), passed=int(row[1]), total_ms=int(row[2]))
