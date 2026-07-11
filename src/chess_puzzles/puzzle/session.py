from __future__ import annotations

from dataclasses import dataclass, field

import chess

from chess_puzzles.move_utils import normalize_promotion
from chess_puzzles.puzzle.model import MoveResult, Puzzle
from chess_puzzles.puzzle.tree import MoveTree, Refutation, TreeNode


@dataclass(slots=True)
class PuzzleSession:
    """Tracks the state of solving one puzzle.

    Owns the board position and move index. Does not touch the UI,
    sounds, or persistence.

    Deviations from the drilled line are classified against the puzzle's
    variation tree (rebuilt from ``pgn_text``): an author-marked mistake is a
    BLUNDER carrying its refutation, an unmarked sibling line is an
    ALTERNATIVE, and anything off-tree is INCORRECT as before. A puzzle
    without variations degenerates to the original expected-move-only check.
    """

    puzzle: Puzzle
    player_color: chess.Color
    board: chess.Board = field(init=False)
    move_index: int = 0
    last_result: MoveResult | None = None
    mistakes: int = 0
    aids_used: int = 0
    last_refutation: Refutation | None = field(init=False, default=None)
    _tree: MoveTree | None = field(init=False, default=None)
    _tree_node: TreeNode | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.board = chess.Board(self.puzzle.initial_fen)
        self._tree = MoveTree.from_pgn_text(self.puzzle.pgn_text, self.puzzle.initial_fen)
        self._tree_node = self._tree.root if self._tree is not None else None

    @property
    def is_complete(self) -> bool:
        return self.move_index >= len(self.puzzle.moves)

    @property
    def expected_move(self) -> chess.Move | None:
        if self.is_complete:
            return None
        return self.puzzle.moves[self.move_index]

    @property
    def current_comment(self) -> str:
        if not self.puzzle.comments:
            return ""
        index = min(self.move_index, len(self.puzzle.comments) - 1)
        return self.puzzle.comments[index]

    def reset(self) -> None:
        self.board = chess.Board(self.puzzle.initial_fen)
        self.move_index = 0
        self.last_result = None
        self.mistakes = 0
        self.aids_used = 0
        self.last_refutation = None
        self._tree_node = self._tree.root if self._tree is not None else None

    def record_aid_used(self) -> None:
        """Count a hint, threat, or overlay reveal against this run.

        Together with the mistake count this feeds into solve-quality
        tracking (stats, spaced repetition, etc.).
        """
        self.aids_used += 1

    def play_user_move(self, move: chess.Move) -> MoveResult:
        self.last_refutation = None
        if self.is_complete:
            self.last_result = MoveResult.COMPLETE
            return self.last_result

        if self.board.turn != self.player_color:
            self.last_result = MoveResult.WAITING
            return self.last_result

        legal_move = normalize_promotion(self.board, move, self.expected_move)
        if legal_move not in self.board.legal_moves:
            self.last_result = MoveResult.ILLEGAL
            return self.last_result

        if legal_move != self.expected_move:
            self.last_result = self._classify_deviation(legal_move)
            return self.last_result

        self._push(legal_move)
        self.last_result = MoveResult.COMPLETE if self.is_complete else MoveResult.CORRECT
        return self.last_result

    def play_computer_move(self) -> chess.Move | None:
        if self.is_complete or self.board.turn == self.player_color:
            return None

        move = self.expected_move
        if move is None:
            return None

        self._push(move)
        self.last_result = MoveResult.COMPLETE if self.is_complete else MoveResult.WAITING
        return move

    def _push(self, move: chess.Move) -> None:
        self.board.push(move)
        self.move_index += 1
        # An off-tree move parks the cursor at None and every later lookup
        # degenerates to INCORRECT; only mainline moves are ever pushed, so
        # this happens only when pgn_text disagrees with puzzle.moves.
        self._tree_node = self._tree_node.child(move) if self._tree_node is not None else None

    def _classify_deviation(self, move: chess.Move) -> MoveResult:
        node = self._tree_node.child(move) if self._tree_node is not None else None
        if node is None:
            self.mistakes += 1
            return MoveResult.INCORRECT
        if node.is_mistake:
            self.mistakes += 1
            self.last_refutation = MoveTree.refutation_of(node)
            return MoveResult.BLUNDER
        return MoveResult.ALTERNATIVE
