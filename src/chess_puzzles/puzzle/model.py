from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import chess


class MoveResult(Enum):
    CORRECT = "correct"
    ILLEGAL = "illegal"
    INCORRECT = "incorrect"
    COMPLETE = "complete"
    WAITING = "waiting"
    # A legal deviation that exists in the puzzle's variation tree: an
    # unmarked sibling line (acceptable, but not the drilled line) ...
    ALTERNATIVE = "alternative"
    # ... or a variation whose first move is NAG-marked ?/??/?! -- a known
    # mistake with a recorded refutation (see puzzle.tree).
    BLUNDER = "blunder"


@dataclass(frozen=True, slots=True)
class Puzzle:
    """A PGN mainline converted into an app-level training item."""

    title: str
    initial_fen: str
    moves: tuple[chess.Move, ...]
    comments: tuple[str, ...] = field(default_factory=tuple)
    headers: dict[str, str] = field(default_factory=dict)
    pgn_text: str = ""
    puzzle_id: str = ""
    ordinal: int = 0
    player_color: chess.Color | None = None
    skip_first_move: bool = False
    theme: str = ""

    @property
    def side_to_move(self) -> chess.Color:
        return chess.Board(self.initial_fen).turn
