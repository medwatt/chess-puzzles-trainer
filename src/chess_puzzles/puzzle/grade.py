from __future__ import annotations

from typing import Literal

Grade = Literal["again", "hard", "good", "easy"]


def grade_solve(mistakes: int, aids: int) -> Grade:
    """Auto-grade a completed solve from how clean it was.

    The single bridge to a future spaced-repetition scheduler: SRS will read
    attempt.grade and add scheduling fields. Time is intentionally NOT used here
    yet (it is stored raw on the attempt for a future policy). A manual override
    UI is a future addition; the attempt already stores the raw signals
    (mistakes, aids, duration_ms) so grading policy can change without migration.
    """
    if mistakes == 0 and aids == 0:
        return "easy"
    if mistakes == 0 and aids <= 1:
        return "good"
    if mistakes <= 1:
        return "hard"
    return "again"
