"""Plays a marked blunder's refutation out on the board.

When the session classifies a move as a BLUNDER, the punishment should be
experienced, not just read: the blunder lands on the board, the refutation
plays out move by move, and the board rewinds to the decision point for a
retry. Pacing follows the same contract as computer replies everywhere else
in the app: silent moves auto-play on the standard reply delay, moves whose
comment has prose wait for the continue key while pause-for-comment is on,
and the final position always waits so the conclusion can be read. Comment
markup (%cal/%csl) is rendered as board arrows and circles at each step.

The solving session never advances during playback -- the walkthrough runs on
a scratch board, so cancelling (navigation, reset) or finishing leaves the
session exactly at the decision point with the mistake already counted.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import chess

from chess_puzzles.constants import COMPUTER_REPLY_DELAY_MS
from chess_puzzles.pgn.comments import annotations_from_comment, strip_annotation_commands
from chess_puzzles.puzzle.tree import Refutation

if TYPE_CHECKING:
    from chess_puzzles.app.main_window import MainWindow


class RefutationPlayback:
    def __init__(self, window: "MainWindow") -> None:
        self._window = window
        self._board: chess.Board | None = None
        self._steps: list[tuple[chess.Move, str]] = []
        self._after_id: str | None = None
        self._finished = False
        self._first_animate = True
        self._played_any = False

    @property
    def active(self) -> bool:
        return self._board is not None

    def start(self, refutation: Refutation, *, animate_first: bool = True) -> None:
        """``animate_first`` carries the input's animate flag: a dragged
        blunder already sits on its target square, exactly like a dragged
        correct move. Refutation replies always animate (they are computer
        moves)."""
        window = self._window
        assert window.session is not None
        self.cancel()
        self._board = window.session.board.copy(stack=False)
        self._steps = [(refutation.move, refutation.comments[0])]
        self._steps.extend(zip(refutation.line, refutation.comments[1:]))
        self._finished = False
        self._first_animate = animate_first
        self._played_any = False
        self._play_next()

    def advance(self) -> bool:
        """Continue-key hook. Returns True when the keypress was consumed:
        plays the next move immediately, or rewinds from the final position."""
        if not self.active:
            return False
        self._cancel_timer()
        if self._finished:
            self._rewind()
        else:
            self._play_next()
        return True

    def cancel(self) -> None:
        """Drop the walkthrough without touching the board view; callers that
        stay on the puzzle use advance()/_rewind, navigation redraws anyway."""
        self._cancel_timer()
        self._board = None
        self._steps = []
        self._finished = False

    def _play_next(self) -> None:
        window = self._window
        board = self._board
        assert board is not None
        move, comment = self._steps.pop(0)
        board_before = board.copy(stack=False)
        board.push(move)
        # The first step is the user's own move and follows the accepted-move
        # conventions: it honors the input's animate flag and flashes (red,
        # where a correct move flashes green). Replies behave like computer
        # moves: always animated, never flashed.
        first = not self._played_any
        self._played_any = True
        window._layout.board.advance_position(board, move, animate=self._first_animate if first else True)
        if first:
            window._layout.board.flash_move(move)
        window.audio.play_move(board_before, move, board)
        annotations = annotations_from_comment(comment)
        if annotations.circles or annotations.arrows:
            window._layout.board.set_annotations(annotations)
        prose = strip_annotation_commands(comment).strip()
        if prose and hasattr(window._layout, "comment_view"):
            window._replace_text(window._layout.comment_view, window._display_comment(comment))
        if not self._steps:
            self._finished = True
            window._status_var.set("Refutation shown - press m to try again.")
            return
        if prose and window._pause_for_comment_var.get():
            window._status_var.set("Blunder: press m to continue.")
            return
        window._status_var.set("Blunder - watch the refutation.")
        self._after_id = window.root.after(COMPUTER_REPLY_DELAY_MS, self._on_timer)

    def _on_timer(self) -> None:
        self._after_id = None
        self._play_next()

    def _rewind(self) -> None:
        window = self._window
        session = window.session
        self.cancel()
        if session is None:
            return
        window._layout.board.advance_position(session.board, None)
        if hasattr(window._layout, "comment_view"):
            window._replace_text(window._layout.comment_view, window._display_comment(session.current_comment))
        window._status_var.set("Back at the position - find the best move.")

    def _cancel_timer(self) -> None:
        if self._after_id is not None:
            self._window.root.after_cancel(self._after_id)
            self._after_id = None
