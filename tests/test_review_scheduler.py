from datetime import UTC, datetime, timedelta

from chess_puzzles.review.scheduler import INTERVALS, SLOW_MS, Rep, effective_grade, next_due

_T0 = datetime(2026, 7, 1, tzinfo=UTC)


def _reps(*grades: str, fast: bool = True) -> list[Rep]:
    duration = 1_000 if fast else SLOW_MS + 1
    return [Rep(_T0 + timedelta(days=i), grade, duration) for i, grade in enumerate(grades)]


def test_fast_flawless_solves_never_enter_review() -> None:
    assert next_due(_reps("easy")) is None
    assert next_due(_reps("easy", "easy", "easy")) is None
    assert next_due([]) is None


def test_failure_enters_at_the_first_rung() -> None:
    history = _reps("again")
    assert next_due(history) == history[-1].at + INTERVALS[0]


def test_clean_solves_climb_and_graduate() -> None:
    assert next_due(_reps("again", "good")) == _reps("again", "good")[-1].at + INTERVALS[1]
    assert next_due(_reps("again", "good", "good")) == _reps("again", "good", "good")[-1].at + INTERVALS[2]
    # Third clean solve climbs past the top rung: graduated.
    assert next_due(_reps("again", "good", "good", "good")) is None


def test_easy_skips_a_rung_and_hard_repeats_it() -> None:
    # again -> easy lands on rung 2 (skipped rung 1).
    history = _reps("again", "easy")
    assert next_due(history) == history[-1].at + INTERVALS[2]
    # hard stays on the same rung.
    history = _reps("again", "hard", "hard")
    assert next_due(history) == history[-1].at + INTERVALS[0]


def test_failing_again_resets_and_revives_a_graduated_puzzle() -> None:
    history = _reps("again", "good", "good", "good", "again")
    assert next_due(history) == history[-1].at + INTERVALS[0]


def test_slow_solves_demote_one_grade_step() -> None:
    assert effective_grade(Rep(_T0, "easy", SLOW_MS + 1)) == "good"
    assert effective_grade(Rep(_T0, "good", SLOW_MS + 1)) == "hard"
    assert effective_grade(Rep(_T0, "again", SLOW_MS + 1)) == "again"
    assert effective_grade(Rep(_T0, "easy", None)) == "easy"  # no clock: no demotion
    # A slow "easy" first solve counts as "good", so the puzzle enters review.
    history = _reps("easy", fast=False)
    assert next_due(history) == history[-1].at + INTERVALS[0]
