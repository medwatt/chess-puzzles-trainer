"""Drill 3 -- hanging pieces: pieces capturable for material gain."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import ClassVar

import chess

from chess_puzzles.vision import analysis
from chess_puzzles.vision.analysis import ColorScope
from chess_puzzles.vision.drill import DrillKind, DrillOption, Question

_SCOPE_CHOICES = (
    ("Both", ColorScope.BOTH),
    ("Side to move", ColorScope.SIDE_TO_MOVE),
    ("Opponent", ColorScope.OPPONENT),
)
# Share of trials that should be "nothing hanging" positions, so the user is
# trained to confidently reject a clean board rather than always hunting.
_NEGATIVE_CHOICES = (
    ("Off", 0.0),
    ("Sometimes", 0.25),
)


@dataclass(frozen=True, slots=True)
class HangingDrill:
    id: ClassVar[str] = "hanging"
    name: ClassVar[str] = "Hanging pieces"
    kind: ClassVar[DrillKind] = DrillKind.MULTI_CLICK
    OPTIONS: ClassVar[tuple[DrillOption, ...]] = (
        DrillOption("scope", "Pieces", _SCOPE_CHOICES),
        DrillOption("include_pawns", "Include pawns"),
        DrillOption("negative_rate", "Negatives", _NEGATIVE_CHOICES),
    )

    scope: ColorScope = ColorScope.OPPONENT
    include_pawns: bool = False
    # Opt-in seam read by VisionSession: when > 0 it draws empty-answer positions
    # at this rate using negative_accepts. Drills without these stay positive-only.
    negative_rate: float = 0.0

    def _answer(self, board: chess.Board) -> frozenset[int]:
        return analysis.hanging_pieces(
            board, scope=self.scope, include_pawns=self.include_pawns, winnable_only=True
        )

    def accepts(self, board: chess.Board) -> bool:
        return bool(self._answer(board))

    def negative_accepts(self, board: chess.Board) -> bool:
        """A position with nothing hanging (under the configured scope)."""
        return not self._answer(board)

    def make_question(self, board: chess.Board, rng: random.Random) -> Question:
        return Question(
            fen=board.fen(),
            orientation=board.turn,
            prompt="Click hanging pieces",
            answer=self._answer(board),
        )


drill = HangingDrill()
