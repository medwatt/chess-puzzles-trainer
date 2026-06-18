from __future__ import annotations

import chess

from chess_puzzles.vision.filters import not_in_check

# White to move is in check (Black queen on a1 rakes the first rank to e1).
_IN_CHECK_FEN = "rnb2Q2/3p1N1k/1p4p1/2ppP2p/7P/1P4P1/P4P2/q3K1NR w - - 0 1"
_QUIET_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def test_not_in_check_rejects_a_position_with_side_to_move_in_check() -> None:
    accept_all = not_in_check(lambda _board: True)
    assert accept_all(chess.Board(_IN_CHECK_FEN)) is False


def test_not_in_check_defers_to_the_wrapped_filter_when_not_in_check() -> None:
    assert not_in_check(lambda _board: True)(chess.Board(_QUIET_FEN)) is True
    assert not_in_check(lambda _board: False)(chess.Board(_QUIET_FEN)) is False
