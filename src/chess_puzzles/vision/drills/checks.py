"""Drill -- available checks: click every square the side to move can check from.

Seeing all checks is the core forcing-move scan behind tactics and mating nets.
The answer is the destination squares of legal checking moves (discoveries count
the square the unmasking piece moves to).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import ClassVar

import chess

from chess_puzzles.vision import analysis
from chess_puzzles.vision.drill import DrillKind, Question


@dataclass(frozen=True, slots=True)
class ChecksDrill:
    id: ClassVar[str] = "checks"
    name: ClassVar[str] = "Available checks"
    kind: ClassVar[DrillKind] = DrillKind.MULTI_CLICK

    def accepts(self, board: chess.Board) -> bool:
        return bool(analysis.checking_destinations(board))

    def make_question(self, board: chess.Board, rng: random.Random) -> Question:
        enemy_king = board.king(not board.turn)
        highlight = frozenset({enemy_king}) if enemy_king is not None else frozenset()
        return Question(
            fen=board.fen(),
            orientation=board.turn,
            prompt="Click squares that give check",
            answer=analysis.checking_destinations(board),
            highlight=highlight,
        )


drill = ChecksDrill()
