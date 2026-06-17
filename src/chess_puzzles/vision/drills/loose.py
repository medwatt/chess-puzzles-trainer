"""Drill 2 -- loose pieces: pieces with as many attackers as defenders.

A loose piece has equal attackers and defenders -- not winnable yet, but one
removed defender or one new attacker away from hanging. Counting includes
X-ray/battery pressure and discounts pinned pieces (see ``vision/analysis.py``).
"""

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
class LooseDrill:
    id: ClassVar[str] = "loose"
    name: ClassVar[str] = "Loose pieces"
    kind: ClassVar[DrillKind] = DrillKind.MULTI_CLICK
    OPTIONS: ClassVar[tuple[DrillOption, ...]] = (
        DrillOption("scope", "Pieces", _SCOPE_CHOICES),
        DrillOption("include_pawns", "Include pawns"),
        DrillOption("contested_only", "Contested only"),
    )

    scope: ColorScope = ColorScope.OPPONENT
    include_pawns: bool = False
    # When set, drop the untouched 0-vs-0 pieces and train only the contested
    # (1-1, 2-2, ...) targets.
    contested_only: bool = False

    def _answer(self, board: chess.Board) -> frozenset[int]:
        return analysis.loose_pieces(
            board,
            scope=self.scope,
            include_pawns=self.include_pawns,
            contested_only=self.contested_only,
        )

    def accepts(self, board: chess.Board) -> bool:
        # Skip positions that contain an outnumbered (hanging) piece: being asked
        # to click only *balanced* pieces while a piece sits in clear danger is
        # confusing, so every piece in a served position is balanced or safe.
        if analysis.hanging_pieces(board, scope=self.scope, include_pawns=self.include_pawns):
            return False
        return bool(self._answer(board))

    def make_question(self, board: chess.Board, rng: random.Random) -> Question:
        return Question(
            fen=board.fen(),
            orientation=board.turn,
            prompt="Click loose pieces",
            answer=self._answer(board),
        )


drill = LooseDrill()
