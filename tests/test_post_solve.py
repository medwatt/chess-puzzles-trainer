"""What happens between the last correct move and the next puzzle.

One rule: the puzzle advances once nothing is waiting on the user. These
tests pin what counts as waiting, and that the same answer holds whether the
line ends on the user's move or the opponent's.
"""

from __future__ import annotations

from dataclasses import replace

import chess

from chess_puzzles.app.app_state import AppState
from chess_puzzles.app.main_window import MainWindow
from chess_puzzles.puzzle import Puzzle, PuzzleSession
from chess_puzzles.settings import AppSettings
from chess_puzzles.shortcuts import CONTINUE_KEY

# 1.e4 solves it; 1.f3 is marked as a mistake and is never played below, so
# it is always available as an "avoided mistake".
TRAP_PGN = """[Event "Trap"]
[Result "*"]

1. e4 ( 1. f3 $4 {weakens the king} 1... e5 2. g4 Qh4# ) *
"""

COMMENTED_PGN = """[Event "Commented"]
[Result "*"]

1. e4 {The point of the whole line.} *
"""


class _Var:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


def _window(pgn: str, comments: tuple[str, ...] = (), **options) -> MainWindow:
    """A MainWindow with only the collaborators the post-solve path touches."""
    puzzle = Puzzle(
        title="P",
        initial_fen=chess.STARTING_FEN,
        moves=(chess.Move.from_uci("e2e4"),),
        comments=comments,
        canonical_pgn=pgn,
    )
    window = MainWindow.__new__(MainWindow)
    window.session = PuzzleSession(puzzle, chess.WHITE)
    window.state = AppState(settings=replace(AppSettings(), **options))
    window._status_var = _Var()
    window._avoided_mistakes = []
    window._seen_mistakes = set()
    return window


def _solve(window: MainWindow) -> None:
    assert window.session is not None
    window.session.play_user_move(chess.Move.from_uci("e2e4"))
    assert window.session.is_complete


def test_avoided_mistake_holds_the_puzzle_open() -> None:
    window = _window(TRAP_PGN)
    _solve(window)

    window._avoided_mistakes = window._mistakes_to_offer()

    assert len(window._avoided_mistakes) == 1
    assert window._post_solve_stop() == (
        f"Puzzle complete - press {CONTINUE_KEY} to see the mistake you avoided."
    )


def test_avoided_mistake_is_not_offered_when_the_option_is_off() -> None:
    window = _window(TRAP_PGN, show_avoided_mistakes=False)
    _solve(window)

    window._avoided_mistakes = window._mistakes_to_offer()

    assert window._avoided_mistakes == []
    assert window._post_solve_stop() is None


def test_a_mistake_already_seen_this_visit_is_not_offered_again() -> None:
    window = _window(TRAP_PGN)
    _solve(window)
    window._seen_mistakes.add((chess.STARTING_FEN, "f2f3"))

    assert window._mistakes_to_offer() == []


def test_final_comment_holds_the_puzzle_open() -> None:
    window = _window(COMMENTED_PGN, comments=("", "Read me."))
    _solve(window)

    assert window._post_solve_stop() == (
        f"Puzzle complete - press {CONTINUE_KEY} for the next puzzle."
    )


def test_final_comment_does_not_stop_when_the_option_is_off() -> None:
    window = _window(COMMENTED_PGN, comments=("", "Read me."), stop_at_comments=False)
    _solve(window)

    assert window._post_solve_stop() is None


def test_final_comment_does_not_stop_when_nothing_would_advance() -> None:
    # With auto-advance off the comment simply stays on screen; promising a
    # key that advances nothing would be a lie.
    window = _window(COMMENTED_PGN, comments=("", "Read me."), auto_advance=False)
    _solve(window)

    assert window._post_solve_stop() is None


def test_an_uncommented_last_move_never_stops() -> None:
    window = _window(COMMENTED_PGN, comments=("", "   "))
    _solve(window)

    assert window._post_solve_stop() is None


def test_a_marked_mistake_is_offered_before_a_final_comment() -> None:
    # Both are waiting: the review comes first, and the comment is still
    # there to be cleared on the next press.
    window = _window(TRAP_PGN, comments=("", "Read me."))
    _solve(window)
    window._avoided_mistakes = window._mistakes_to_offer()

    assert "mistake you avoided" in (window._post_solve_stop() or "")


OPPONENT_LAST_PGN = """[Event "Opponent last"]
[Result "*"]

1. e4 e5 {Final word.} *
"""


def test_a_line_ending_on_the_opponents_move_stops_the_same_way() -> None:
    # This is the case that used to differ: the pause before a reply fired,
    # but completion itself checked nothing, so the last comment was skipped
    # whenever the opponent had the final move.
    puzzle = Puzzle(
        title="P",
        initial_fen=chess.STARTING_FEN,
        moves=(chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")),
        comments=("", "", "Final word."),
        canonical_pgn=OPPONENT_LAST_PGN,
    )
    window = MainWindow.__new__(MainWindow)
    window.session = PuzzleSession(puzzle, chess.WHITE)
    window.state = AppState(settings=AppSettings())
    window._status_var = _Var()
    window._avoided_mistakes = []
    window._seen_mistakes = set()

    window.session.play_user_move(chess.Move.from_uci("e2e4"))
    window.session.play_computer_move()
    assert window.session.is_complete

    assert window._post_solve_stop() == (
        f"Puzzle complete - press {CONTINUE_KEY} for the next puzzle."
    )
