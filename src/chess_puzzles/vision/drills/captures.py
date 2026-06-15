"""Drill -- available captures: click pieces that can be legally captured."""

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
_NEGATIVE_CHOICES = (
    ("Off", 0.0),
    ("Sometimes", 0.25),
)


@dataclass(frozen=True, slots=True)
class CapturesDrill:
    id: ClassVar[str] = "captures"
    name: ClassVar[str] = "Available captures"
    kind: ClassVar[DrillKind] = DrillKind.MULTI_CLICK
    OPTIONS: ClassVar[tuple[DrillOption, ...]] = (
        DrillOption("scope", "Pieces", _SCOPE_CHOICES),
        DrillOption("include_pawns", "Include pawns"),
        DrillOption("negative_rate", "Negatives", _NEGATIVE_CHOICES),
    )

    scope: ColorScope = ColorScope.OPPONENT
    include_pawns: bool = True
    negative_rate: float = 0.0

    def _answer(self, board: chess.Board) -> frozenset[int]:
        return analysis.capturable(board, scope=self.scope, include_pawns=self.include_pawns)

    def accepts(self, board: chess.Board) -> bool:
        return bool(self._answer(board))

    def negative_accepts(self, board: chess.Board) -> bool:
        return not self._answer(board)

    def make_question(self, board: chess.Board, rng: random.Random) -> Question:
        return Question(
            fen=board.fen(),
            orientation=board.turn,
            prompt="Click capturable pieces",
            answer=self._answer(board),
        )


drill = CapturesDrill()
