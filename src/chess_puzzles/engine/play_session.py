from __future__ import annotations

from dataclasses import dataclass, field

import chess

from chess_puzzles.move_utils import normalize_promotion


@dataclass(slots=True)
class EnginePlaySession:
    """Mutable board state for free play against an engine."""

    initial_board: chess.Board
    human_color: chess.Color
    board: chess.Board = field(init=False)

    def __post_init__(self) -> None:
        self.board = self.initial_board.copy(stack=False)

    @property
    def is_human_turn(self) -> bool:
        return self.board.turn == self.human_color

    def reset(self) -> None:
        self.board = self.initial_board.copy(stack=False)

    def play_user_move(self, move: chess.Move) -> chess.Move | None:
        """Play a legal move for whichever side is to move (the human may move for the engine)."""
        legal_move = normalize_promotion(self.board, move)
        if legal_move not in self.board.legal_moves:
            return None
        self.board.push(legal_move)
        return legal_move

    def takeback(self) -> chess.Move | None:
        return self.board.pop() if self.board.move_stack else None

    def play_engine_move(self, move: chess.Move) -> bool:
        if self.is_human_turn or move not in self.board.legal_moves:
            return False
        self.board.push(move)
        return True
