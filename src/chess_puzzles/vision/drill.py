"""The drill abstraction -- the plug-and-play seam for board vision.

A drill knows only two things: which positions it accepts, and how to turn an
accepted position into a question with a ground-truth answer. Everything else --
collecting clicks, grading, timing, flashing, storing, stats -- is identical
across drills and lives in ``VisionSession``. Adding a drill is therefore one
new module in ``drills/`` plus one registry entry.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

import chess


class DrillKind(Enum):
    """How the user submits an answer."""

    SINGLE_CLICK = "single_click"  # first click is the answer (e.g. localization)
    MULTI_CLICK = "multi_click"  # click many squares, then submit


@dataclass(frozen=True, slots=True)
class Question:
    """A single posed trial: a position, a prompt, and the correct squares."""

    fen: str
    orientation: chess.Color
    prompt: str
    answer: frozenset[int]
    highlight: frozenset[int] = field(default_factory=frozenset)
    label: str | None = None


@dataclass(frozen=True, slots=True)
class TrialResult:
    """The grading of one answered question. ``passed`` is an exact match."""

    correct: frozenset[int]  # clicked and right (true positives)
    missed: frozenset[int]  # should have been clicked (false negatives)
    wrong: frozenset[int]  # clicked but wrong (false positives)
    passed: bool
    elapsed_ms: int

    @classmethod
    def grade(cls, answer: frozenset[int], clicks: frozenset[int], elapsed_ms: int) -> "TrialResult":
        correct = answer & clicks
        return cls(
            correct=correct,
            missed=answer - clicks,
            wrong=clicks - answer,
            passed=clicks == answer,
            elapsed_ms=elapsed_ms,
        )


@dataclass(frozen=True, slots=True)
class DrillOption:
    """A tunable knob a drill exposes to the UI, mapping to a drill dataclass field.

    ``choices`` of ``None`` means a boolean toggle; otherwise it is a list of
    ``(label, value)`` pairs rendered as a dropdown. The options panel reads these
    generically, so a new drill's knobs appear in the UI with no UI changes.
    """

    key: str
    label: str
    choices: tuple[tuple[str, object], ...] | None = None


class Drill(Protocol):
    """A board vision drill. Implementations live in ``vision/drills/``."""

    id: str
    name: str
    kind: DrillKind

    def accepts(self, board: chess.Board) -> bool:
        """Whether a position can produce a (non-trivial) question for this drill."""
        ...

    def make_question(self, board: chess.Board, rng: random.Random) -> Question:
        """Build a question from a board the drill has already accepted."""
        ...


# --- Optional drill capabilities -------------------------------------------
# Beyond the required Protocol above, a drill may opt into extra behaviour just
# by declaring the matching attribute. These accessors are the single, typed
# home for that knowledge, so consumers never scatter getattr() across the code
# and the full set of optional capabilities is readable in one place. To add a
# capability: add one accessor here and read the attribute through it.


def drill_options(drill: Drill) -> tuple[DrillOption, ...]:
    """The tunable knobs a drill exposes to the UI (empty when it has none)."""
    return getattr(drill, "OPTIONS", ())


def shows_coordinates(drill: Drill) -> bool:
    """Whether the board may show file/rank coordinates for this drill."""
    return getattr(drill, "show_coordinates", True)


def negative_rate(drill: Drill) -> float:
    """Fraction of trials that should pose an empty-answer (negative) position."""
    return getattr(drill, "negative_rate", 0.0)


def negative_accepts(drill: Drill) -> Callable[[chess.Board], bool] | None:
    """Predicate selecting empty-answer positions, if the drill supports negatives."""
    return getattr(drill, "negative_accepts", None)
