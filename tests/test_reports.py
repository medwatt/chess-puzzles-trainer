from __future__ import annotations

from pathlib import Path

from chess_puzzles.dialogs.statistics import _summary_rows
from chess_puzzles.reports import AttemptSummary, attempt_summary, format_duration_ms
from chess_puzzles.store import Attempt, UserStore


def _attempt(
    puzzle_id: str,
    at: str,
    outcome: str,
    duration_ms: int | None = None,
    *,
    mistakes: int = 0,
) -> Attempt:
    return Attempt(
        puzzle_id=puzzle_id,
        at=at,
        outcome=outcome,
        mistakes=mistakes,
        aids=0,
        grade="easy" if outcome == "solved" else "again",
        duration_ms=duration_ms,
    )


def test_attempt_summary_filters_by_since_and_puzzle_ids(tmp_path: Path) -> None:
    store = UserStore.open(tmp_path / "u.db")
    store.record_attempt(_attempt("p1", "2026-01-01T00:00:00Z", "solved", 30_000))
    store.record_attempt(_attempt("p1", "2026-01-02T00:00:00Z", "gave_up"))
    store.record_attempt(_attempt("p2", "2026-01-02T00:01:00Z", "solved", 90_000))

    summary = attempt_summary(store.connection, since="2026-01-02T00:00:00Z", puzzle_ids={"p1", "p2"})

    assert summary.attempted == 2
    assert summary.solved == 1
    assert summary.solved_percent == 50
    assert summary.gave_up == 1
    assert summary.total_ms == 90_000
    assert summary.avg_ms == 45_000


def test_attempt_summary_counts_time_for_all_attempts(tmp_path: Path) -> None:
    store = UserStore.open(tmp_path / "u.db")
    store.record_attempt(_attempt("p1", "2026-01-01T00:00:00Z", "solved", 30_000))
    store.record_attempt(_attempt("p2", "2026-01-01T00:01:00Z", "solved", 90_000, mistakes=1))
    store.record_attempt(_attempt("p3", "2026-01-01T00:02:00Z", "gave_up", 60_000))

    summary = attempt_summary(store.connection)

    assert summary.attempted == 3
    assert summary.solved == 1
    assert summary.solved_percent == 33
    assert summary.gave_up == 1
    assert summary.total_ms == 180_000
    assert summary.avg_ms == 60_000


def test_attempt_summary_empty_puzzle_filter(tmp_path: Path) -> None:
    store = UserStore.open(tmp_path / "u.db")
    store.record_attempt(_attempt("p1", "2026-01-01T00:00:00Z", "solved", 30_000))

    summary = attempt_summary(store.connection, puzzle_ids=set())

    assert summary.attempted == 0
    assert summary.solved_percent is None


def test_summary_rows_with_attempts() -> None:
    rows = dict(_summary_rows(AttemptSummary(attempted=4, solved=3, gave_up=1, total_ms=120_000)))
    assert rows["Attempted"] == "4"
    assert rows["Solved"] == "3 (75%)"
    assert rows["Gave up"] == "1"
    assert rows["Average time"] == "0:30"


def test_summary_rows_empty() -> None:
    rows = dict(_summary_rows(AttemptSummary(attempted=0, solved=0, gave_up=0, total_ms=0)))
    assert rows["Solved"] == "0"
    assert rows["Average time"] == "-"


def test_format_duration_ms() -> None:
    assert format_duration_ms(None) == "-"
    assert format_duration_ms(0) == "0:00"
    assert format_duration_ms(65_000) == "1:05"
    assert format_duration_ms(3_665_000) == "1:01:05"
