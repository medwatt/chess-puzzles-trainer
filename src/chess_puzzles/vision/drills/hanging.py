"""Drill -- hanging pieces: pieces capturable for material gain."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import ClassVar

import chess

from chess_puzzles.vision import analysis
from chess_puzzles.vision.analysis import ColorScope
from chess_puzzles.vision.drill import NEGATIVE_CHOICES, SCOPE_CHOICES, DrillKind, DrillOption, Question


@dataclass(frozen=True, slots=True)
class HangingDrill:
    id: ClassVar[str] = "hanging"
    name: ClassVar[str] = "Hanging pieces"
    kind: ClassVar[DrillKind] = DrillKind.MULTI_CLICK
    OPTIONS: ClassVar[tuple[DrillOption, ...]] = (
        DrillOption("scope", "Pieces", SCOPE_CHOICES),
        DrillOption("include_pawns", "Include pawns"),
        DrillOption("winnable", "Winnable"),
        DrillOption("negative_rate", "Negatives", NEGATIVE_CHOICES),
    )

    scope: ColorScope = ColorScope.OPPONENT
    include_pawns: bool = False
    # When set (the default), "hanging" means value-aware winnable (a piece losing
    # material to a cheaper attacker, e.g. a knight attacked by a pawn yet defended
    # once) rather than the pure count of more attackers than defenders. Turn off to
    # get the strict count-based set (more attackers than defenders, then winnable).
    winnable: bool = True
    # Opt-in seam read by VisionSession: when > 0 it draws empty-answer positions
    # at this rate using negative_accepts. Drills without these stay positive-only.
    negative_rate: float = 0.0

    def _answer(self, board: chess.Board) -> frozenset[int]:
        if self.winnable:
            return analysis.winnable_pieces(
                board, scope=self.scope, include_pawns=self.include_pawns
            )
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
