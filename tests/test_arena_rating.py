from __future__ import annotations

from pathlib import Path

from chess_puzzles.arena.rating import (
    RatedAttempt,
    elo_v1_rating,
    is_win,
    session_rating,
)
from chess_puzzles.store import Attempt, UserStore


def _attempt(puzzle_id: str, rating: int | None, outcome: str = "solved", mistakes: int = 0, aids: int = 0) -> RatedAttempt:
    return RatedAttempt(puzzle_id, rating, outcome, mistakes, aids)


def test_empty_history_is_start_rating() -> None:
    assert elo_v1_rating(1500, []) == 1500.0


def test_clean_solve_raises_rating_and_failure_lowers_it() -> None:
    up = elo_v1_rating(1500, [_attempt("a", 1500)])
    down = elo_v1_rating(1500, [_attempt("a", 1500, outcome="gave_up")])
    assert up == 1500 + 20  # K=40, expected 0.5
    assert down == 1500 - 20


def test_mistake_or_aid_makes_the_rated_result_a_loss() -> None:
    assert not is_win(_attempt("a", 1500, mistakes=1))
    assert not is_win(_attempt("a", 1500, aids=1))
    with_mistake = elo_v1_rating(1500, [_attempt("a", 1500, mistakes=1)])
    assert with_mistake < 1500


def test_only_first_attempt_per_puzzle_counts() -> None:
    first_only = elo_v1_rating(1500, [_attempt("a", 1500, outcome="gave_up")])
    with_resolve = elo_v1_rating(
        1500,
        [_attempt("a", 1500, outcome="gave_up"), _attempt("a", 1500)],
    )
    assert with_resolve == first_only


def test_null_puzzle_rating_rows_are_ignored() -> None:
    assert elo_v1_rating(1500, [_attempt("a", None)]) == 1500.0
    # A legacy/unrated row is outside rating policy and therefore cannot hide
    # the first later attempt that actually carries a puzzle rating.
    later = elo_v1_rating(1500, [_attempt("a", None), _attempt("a", 1500)])
    assert later == 1500 + 20


def test_k_drops_after_twenty_rated_attempts() -> None:
    # 20 wins against equally-rated puzzles at K=40, then one more at K=20.
    attempts = [_attempt(f"p{i}", 1500) for i in range(21)]
    partial = elo_v1_rating(1500, attempts[:20])
    full = elo_v1_rating(1500, attempts)
    last_gain = full - partial
    # Expected score > 0.5 is impossible here (rating grew above the puzzles),
    # so the last step must be smaller than half of K=40's midpoint step and
    # bounded by K=20.
    assert 0 < last_gain < 20


def test_session_rating_reads_one_arena_in_id_order(tmp_path: Path) -> None:
    store = UserStore.open(tmp_path / "userdata.db")
    base = dict(at="2026-07-15T00:00:00Z", grade="good", database_path="/tmp/a.cpdb")
    store.record_attempt(
        Attempt(puzzle_id="a", outcome="gave_up", mistakes=0, aids=0,
                database_id="arena-1", puzzle_rating=1500, **base)
    )
    # A different deck's attempt must not affect arena-1.
    store.record_attempt(
        Attempt(puzzle_id="b", outcome="solved", mistakes=0, aids=0,
                database_id="other", puzzle_rating=1500, **base)
    )
    # Review re-solve of the same puzzle in arena-1: not the first attempt.
    store.record_attempt(
        Attempt(puzzle_id="a", outcome="solved", mistakes=0, aids=0,
                database_id="arena-1", puzzle_rating=1500, **base)
    )
    assert session_rating(store.connection, "arena-1", 1500) == 1500 - 20


def test_first_attempt_losses_track_history_not_current_state(tmp_path: Path) -> None:
    from chess_puzzles.arena.rating import first_attempt_losses

    store = UserStore.open(tmp_path / "userdata.db")
    base = dict(at="2026-07-16T00:00:00Z", grade="good", database_path="", puzzle_rating=1500)
    losing = dict(outcome="gave_up", mistakes=0, aids=0)
    clean = dict(outcome="solved", mistakes=0, aids=0)

    # a: first loss, later clean review -> stays a historical mistake.
    store.record_attempt(Attempt(puzzle_id="a", database_id="arena-1", **losing, **base))
    store.record_attempt(Attempt(puzzle_id="a", database_id="arena-1", **clean, **base))
    # b: clean first solve, later failed review -> never a historical mistake.
    store.record_attempt(Attempt(puzzle_id="b", database_id="arena-1", **clean, **base))
    store.record_attempt(Attempt(puzzle_id="b", database_id="arena-1", **losing, **base))
    # c: loss in a DIFFERENT arena -> scoped out.
    store.record_attempt(Attempt(puzzle_id="c", database_id="arena-2", **losing, **base))
    # d: aided solve counts as a rated loss.
    store.record_attempt(
        Attempt(puzzle_id="d", database_id="arena-1", outcome="solved", mistakes=0, aids=1, **base)
    )
    # e: an old null-rated row is not a rated result; the following rated loss
    # is the first result historical arena review should see.
    store.record_attempt(
        Attempt(
            puzzle_id="e", database_id="arena-1", outcome="solved", mistakes=0,
            aids=0, puzzle_rating=None, at=base["at"], grade=base["grade"],
            database_path=base["database_path"],
        )
    )
    store.record_attempt(Attempt(puzzle_id="e", database_id="arena-1", **losing, **base))

    assert first_attempt_losses(store.connection, "arena-1") == ["a", "d", "e"]
    assert first_attempt_losses(store.connection, "arena-2") == ["c"]


def test_migration_adds_rating_column_and_index(tmp_path: Path) -> None:
    store = UserStore.open(tmp_path / "userdata.db")
    columns = {
        row[1] for row in store.connection.execute("PRAGMA table_info(attempt)")
    }
    assert "puzzle_rating" in columns
    indexes = {
        row[1] for row in store.connection.execute("PRAGMA index_list(attempt)")
    }
    assert "idx_attempt_database_puzzle" in indexes
