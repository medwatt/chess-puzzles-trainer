"""The drill-agnostic state machine for a board vision session.

It pulls a position from the source, asks the drill for a question, collects the
user's clicks, grades on submit (exact match), and keeps running session stats.
It knows nothing about any specific drill or about the UI/storage, mirroring how
``PuzzleSession`` sits beneath ``MainWindow``.
"""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass

from chess_puzzles.vision.drill import (
    Drill,
    DrillKind,
    Question,
    TrialResult,
    negative_accepts,
    negative_rate,
)
from chess_puzzles.vision.filters import Accepts, not_in_check
from chess_puzzles.vision.source import PositionSource


@dataclass(slots=True)
class SessionStats:
    trials: int = 0
    passed: int = 0
    total_ms: int = 0
    streak: int = 0  # current run of consecutive passes, reset by any miss

    @property
    def accuracy(self) -> float:
        return 100.0 * self.passed / self.trials if self.trials else 0.0

    @property
    def average_ms(self) -> int:
        return self.total_ms // self.trials if self.trials else 0


class VisionSession:
    def __init__(
        self,
        drill: Drill,
        source: PositionSource,
        *,
        rng: random.Random | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.drill = drill
        self._source = source
        self._rng = rng or random.Random()
        self._clock = clock
        self.question: Question | None = None
        self.stats = SessionStats()
        self._clicks: set[int] = set()
        self._started_at: float | None = None

    @property
    def is_single_click(self) -> bool:
        return self.drill.kind is DrillKind.SINGLE_CLICK

    @property
    def clicks(self) -> frozenset[int]:
        return frozenset(self._clicks)

    def next_question(self) -> Question:
        """Draw a fresh accepted position and pose its question."""
        board = self._source.next(self._accepts_for_trial(), self._rng)
        self.question = self.drill.make_question(board, self._rng)
        self._clicks = set()
        self._started_at = self._clock()
        return self.question

    def _accepts_for_trial(self) -> Accepts:
        """Usually the drill's positive filter, but occasionally an empty-answer
        one for drills that opt into negative trials. Drills that don't expose
        negatives are unaffected. (A rarely-satisfied negative filter makes the
        source scan harder, so keep negative positions reasonably common.)

        Every filter is wrapped to reject positions where the side to move is in
        check: the attacker/defender counts collapse there (only check-resolving
        captures are legal), manufacturing confusing "loose"/"hanging" answers,
        and being shown a board you must respond to a check on is jarring for a
        calm perception drill."""
        rate = negative_rate(self.drill)
        negative = negative_accepts(self.drill)
        if rate and negative is not None and self._rng.random() < rate:
            return not_in_check(negative)
        return not_in_check(self.drill.accepts)

    def toggle(self, square: int) -> None:
        """Register a click. Single-click drills keep only the latest square."""
        if self.is_single_click:
            self._clicks = {square}
        elif square in self._clicks:
            self._clicks.discard(square)
        else:
            self._clicks.add(square)

    def submit(self) -> TrialResult:
        if self.question is None:
            raise RuntimeError("submit() called before next_question()")
        started = self._started_at if self._started_at is not None else self._clock()
        elapsed_ms = max(0, int((self._clock() - started) * 1000))
        result = TrialResult.grade(self.question.answer, frozenset(self._clicks), elapsed_ms)
        self.stats.trials += 1
        self.stats.passed += int(result.passed)
        self.stats.total_ms += elapsed_ms
        self.stats.streak = self.stats.streak + 1 if result.passed else 0
        return result
