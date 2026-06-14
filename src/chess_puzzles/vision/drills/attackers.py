"""Drill -- attackers of a piece: click every enemy piece attacking a marked one.

The counting primitive under every capture/exchange: how many enemy pieces attack
a piece (against how many friendly pieces defend it) decides whether it can be won.
Friendly defenders are deliberately excluded -- they are not attackers.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import ClassVar

import chess

from chess_puzzles.vision import analysis
from chess_puzzles.vision.drill import DrillKind, Question


@dataclass(frozen=True, slots=True)
class AttackersDrill:
    id: ClassVar[str] = "attackers"
    name: ClassVar[str] = "Attackers of a square"
    kind: ClassVar[DrillKind] = DrillKind.MULTI_CLICK

    def _candidates(self, board: chess.Board) -> list[int]:
        # Only pieces that actually have an enemy attacker, so the answer is never
        # empty and never a piece that is merely defended.
        return [sq for sq in board.piece_map() if analysis.attackers_of_piece(board, sq)]

    def accepts(self, board: chess.Board) -> bool:
        return bool(self._candidates(board))

    def make_question(self, board: chess.Board, rng: random.Random) -> Question:
        target = rng.choice(self._candidates(board))
        return Question(
            fen=board.fen(),
            orientation=board.turn,
            prompt="Click attackers of the marked piece",
            answer=analysis.attackers_of_piece(board, target),
            highlight=frozenset({target}),
        )


drill = AttackersDrill()
