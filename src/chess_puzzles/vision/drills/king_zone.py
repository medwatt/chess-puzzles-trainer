"""Drill -- king zone: click every attacked square next to a king."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import ClassVar

import chess

from chess_puzzles.vision import analysis
from chess_puzzles.vision.drill import DrillKind, Question


@dataclass(frozen=True, slots=True)
class KingZoneDrill:
    id: ClassVar[str] = "king-zone"
    name: ClassVar[str] = "King zone"
    kind: ClassVar[DrillKind] = DrillKind.MULTI_CLICK

    def _candidates(self, board: chess.Board) -> list[chess.Color]:
        return [color for color in (chess.WHITE, chess.BLACK) if analysis.king_zone_attacked(board, color)]

    def accepts(self, board: chess.Board) -> bool:
        return bool(self._candidates(board))

    def make_question(self, board: chess.Board, rng: random.Random) -> Question:
        king_color = rng.choice(self._candidates(board))
        answer = analysis.king_zone_attacked(board, king_color)
        king_square = board.king(king_color)
        highlight = frozenset({king_square}) if king_square is not None else frozenset()
        return Question(
            fen=board.fen(),
            orientation=king_color,
            prompt="Click attacked squares around the king",
            answer=answer,
            highlight=highlight,
        )


drill = KingZoneDrill()
