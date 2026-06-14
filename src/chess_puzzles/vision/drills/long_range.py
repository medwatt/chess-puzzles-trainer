"""Drill -- long-range attacks: click sliders aimed at enemy pieces."""

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


@dataclass(frozen=True, slots=True)
class LongRangeAttackDrill:
    id: ClassVar[str] = "long-range"
    name: ClassVar[str] = "Long-range attacks"
    kind: ClassVar[DrillKind] = DrillKind.MULTI_CLICK
    OPTIONS: ClassVar[tuple[DrillOption, ...]] = (
        DrillOption("scope", "Pieces", _SCOPE_CHOICES),
        DrillOption("include_pawns", "Include pawns"),
    )

    scope: ColorScope = ColorScope.SIDE_TO_MOVE
    include_pawns: bool = False

    def _answer(self, board: chess.Board) -> frozenset[int]:
        return analysis.long_range_attackers(board, scope=self.scope, include_pawns=self.include_pawns)

    def accepts(self, board: chess.Board) -> bool:
        return bool(self._answer(board))

    def make_question(self, board: chess.Board, rng: random.Random) -> Question:
        return Question(
            fen=board.fen(),
            orientation=board.turn,
            prompt="Click long-range attackers",
            answer=self._answer(board),
        )


drill = LongRangeAttackDrill()
