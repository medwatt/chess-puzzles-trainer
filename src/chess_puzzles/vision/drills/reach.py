"""Drill 4 -- piece reach: click every square a highlighted piece attacks.

One parameterized drill, registered once per piece type, so the knight / bishop
/ rook / queen variants are data, not four classes.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import ClassVar

import chess

from chess_puzzles.vision import analysis
from chess_puzzles.vision.drill import DrillKind, DrillOption, Question


_TYPE_NAMES: dict[chess.PieceType, str] = {
    chess.KNIGHT: "knight",
    chess.BISHOP: "bishop",
    chess.ROOK: "rook",
    chess.QUEEN: "queen",
}


@dataclass(frozen=True, slots=True)
class ReachDrill:
    kind: ClassVar[DrillKind] = DrillKind.MULTI_CLICK
    OPTIONS: ClassVar[tuple[DrillOption, ...]] = (
        DrillOption("include_defended_squares", "Include defended squares"),
    )

    piece_type: chess.PieceType
    include_defended_squares: bool = True

    @property
    def id(self) -> str:
        return f"reach-{_TYPE_NAMES[self.piece_type]}"

    @property
    def name(self) -> str:
        return f"{_TYPE_NAMES[self.piece_type].capitalize()} reach"

    def accepts(self, board: chess.Board) -> bool:
        return bool(analysis.pieces_of_types(board, (self.piece_type,)))

    def make_question(self, board: chess.Board, rng: random.Random) -> Question:
        square = rng.choice(analysis.pieces_of_types(board, (self.piece_type,)))
        piece = board.piece_at(square)
        assert piece is not None  # accept() guaranteed a piece of this type
        answer = analysis.reach(board, square, include_defended_squares=self.include_defended_squares)
        return Question(
            fen=board.fen(),
            orientation=piece.color,
            prompt="Click this piece's squares",
            answer=answer,
            highlight=frozenset({square}),
        )


drills: tuple[ReachDrill, ...] = tuple(
    ReachDrill(piece_type) for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
)
