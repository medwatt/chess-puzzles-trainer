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
# Share of trials that should be "nothing loose" positions, so the user is
# trained to confidently reject a calm board rather than always finding a target.
_NEGATIVE_CHOICES = (
    ("Off", 0.0),
    ("Sometimes", 0.25),
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
        DrillOption("negative_rate", "Negatives", _NEGATIVE_CHOICES),
    )

    scope: ColorScope = ColorScope.OPPONENT
    include_pawns: bool = False
    # When set, drop the untouched 0-vs-0 pieces and train only the contested
    # (1-1, 2-2, ...) targets.
    contested_only: bool = False
    # Opt-in seam read by VisionSession: when > 0 it draws empty-answer positions
    # at this rate using negative_accepts. Drills without these stay positive-only.
    negative_rate: float = 0.0

    def _answer(self, board: chess.Board) -> frozenset[int]:
        return analysis.loose_pieces(
            board,
            scope=self.scope,
            include_pawns=self.include_pawns,
            contested_only=self.contested_only,
        )

    def _has_hanging(self, board: chess.Board) -> bool:
        # Skip positions that contain an outnumbered (hanging) piece: being asked
        # to judge balanced pieces while a piece sits in clear danger is confusing,
        # so every served position (positive or negative) is free of hanging pieces.
        return bool(analysis.hanging_pieces(board, scope=self.scope, include_pawns=self.include_pawns))

    def accepts(self, board: chess.Board) -> bool:
        return not self._has_hanging(board) and bool(self._answer(board))

    def negative_accepts(self, board: chess.Board) -> bool:
        """A calm position with nothing loose (and nothing hanging) in scope."""
        return not self._has_hanging(board) and not self._answer(board)

    def make_question(self, board: chess.Board, rng: random.Random) -> Question:
        return Question(
            fen=board.fen(),
            orientation=board.turn,
            prompt="Click loose pieces",
            answer=self._answer(board),
        )


drill = LooseDrill()
