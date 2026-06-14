from __future__ import annotations

import pytest

from chess_puzzles.puzzle.grade import grade_solve


@pytest.mark.parametrize(
    ("mistakes", "aids", "expected"),
    [(0, 0, "easy"), (0, 1, "good"), (1, 0, "hard"), (3, 2, "again")],
)
def test_grade_solve(mistakes: int, aids: int, expected: str) -> None:
    assert grade_solve(mistakes, aids) == expected
