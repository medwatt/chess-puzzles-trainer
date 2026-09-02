from dataclasses import replace
from datetime import UTC, datetime, timedelta

from chess_puzzles.review.scheduler import (
    INTERVALS,
    SLOW_BASE_MS,
    SLOW_MS,
    SLOW_PER_EXTRA_DECISION_MS,
    Rep,
    effective_grade,
    next_due,
    slow_threshold_ms,
)

_T0 = datetime(2026, 7, 1, tzinfo=UTC)


def _reps(*grades: str, fast: bool = True) -> list[Rep]:
    duration = 1_000 if fast else SLOW_MS + 1
    return [Rep(_T0 + timedelta(days=i), grade, duration) for i, grade in enumerate(grades)]


def test_a_fast_flawless_first_solve_enters_at_the_top_rung() -> None:
    # One good solve is not enough evidence to drop a puzzle for good, but it
    # earns the longest interval rather than a review tomorrow.
    history = _reps("easy")
    assert next_due(history) == history[-1].at + INTERVALS[-1]


def test_a_second_fast_flawless_solve_graduates_it() -> None:
    assert next_due(_reps("easy", "easy")) is None
    assert next_due(_reps("easy", "easy", "easy")) is None


def test_no_history_is_never_due() -> None:
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


def test_the_speed_budget_scales_with_solution_length() -> None:
    # A mate in one and a six-move combination cannot share a stopwatch.
    assert slow_threshold_ms(1) == SLOW_BASE_MS
    assert slow_threshold_ms(2) == SLOW_BASE_MS
    assert slow_threshold_ms(3) == SLOW_BASE_MS + SLOW_PER_EXTRA_DECISION_MS
    assert slow_threshold_ms(7) == SLOW_BASE_MS + 3 * SLOW_PER_EXTRA_DECISION_MS
    # Strictly increasing with length, so a longer line is never judged harder.
    budgets = [slow_threshold_ms(plies) for plies in range(1, 12)]
    assert budgets == sorted(budgets)


def test_attempts_without_a_recorded_length_keep_the_flat_threshold() -> None:
    # History predating the column must not be regraded by a budget derived
    # from a length nobody recorded.
    assert slow_threshold_ms(None) == SLOW_MS


def test_a_long_solve_is_flawless_on_a_long_line_and_slow_on_a_short_one() -> None:
    took = Rep(_T0, "easy", SLOW_BASE_MS + 1)
    assert effective_grade(replace(took, solution_plies=1)) == "good"      # slow
    assert effective_grade(replace(took, solution_plies=7)) == "easy"      # fine

    # And the demotion still bites once the longer budget is exceeded.
    very_slow = Rep(_T0, "easy", slow_threshold_ms(7) + 1, solution_plies=7)
    assert effective_grade(very_slow) == "good"


def test_a_slow_first_solve_enters_at_the_bottom_rung_not_the_top() -> None:
    # Demoted to "good", so it is not treated as an instantly-known pattern.
    history = [Rep(_T0, "easy", slow_threshold_ms(3) + 1, solution_plies=3)]
    assert next_due(history) == history[-1].at + INTERVALS[0]
