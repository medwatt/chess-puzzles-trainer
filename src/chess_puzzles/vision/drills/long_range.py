"""Drill -- long-range attacks: click sliders aimed at enemy pieces."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import ClassVar

import chess

from chess_puzzles.vision import analysis
from chess_puzzles.vision.analysis import ColorScope
from chess_puzzles.vision.drill import SCOPE_CHOICES, DrillKind, DrillOption, Question


@dataclass(frozen=True, slots=True)
class LongRangeAttackDrill:
    id: ClassVar[str] = "long-range"
    name: ClassVar[str] = "Long-range attacks"
    kind: ClassVar[DrillKind] = DrillKind.MULTI_CLICK
    OPTIONS: ClassVar[tuple[DrillOption, ...]] = (
        DrillOption("scope", "Pieces", SCOPE_CHOICES),
        DrillOption("include_pawns", "Include pawns"),
    )

    scope: ColorScope = ColorScope.SIDE_TO_MOVE
    include_pawns: bool = False

    def _targets(self, board: chess.Board) -> dict[int, frozenset[int]]:
        return analysis.long_range_attack_targets(board, scope=self.scope, include_pawns=self.include_pawns)

    def accepts(self, board: chess.Board) -> bool:
        return bool(self._targets(board))

    def make_question(self, board: chess.Board, rng: random.Random) -> Question:
        targets = self._targets(board)
        return Question(
            fen=board.fen(),
            orientation=board.turn,
            prompt="Click long-range attackers",
            answer=frozenset(targets),
            # Slider -> attacked piece, shown with the solution so a missed
            # attacker's line is visible at a glance.
            feedback_arrows=frozenset(
                (origin, target) for origin, target_squares in targets.items() for target in target_squares
            ),
        )


drill = LongRangeAttackDrill()
