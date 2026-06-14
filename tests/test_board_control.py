from __future__ import annotations

import chess

from chess_puzzles.board.control import contested_square_margins, squares_in_danger


def test_undefended_attacked_pawn_is_flagged() -> None:
    board = chess.Board("8/8/5n2/8/4P3/8/8/K6k w - - 0 1")

    assert squares_in_danger(board) == frozenset({chess.E4})


def test_defended_pawn_attacked_by_knight_is_safe() -> None:
    board = chess.Board("8/8/5n2/8/4P3/3P4/8/K6k w - - 0 1")

    assert squares_in_danger(board) == frozenset()


def test_defended_queen_attacked_by_cheaper_pawn_is_flagged() -> None:
    board = chess.Board("k7/8/8/2p5/3Q4/8/8/3R3K w - - 0 1")

    danger = squares_in_danger(board)

    assert chess.D4 in danger
    # The pawn itself hangs to the queen, so both sides get flagged.
    assert chess.C5 in danger


def test_attacked_king_is_always_flagged() -> None:
    board = chess.Board("k7/8/8/8/8/8/8/R6K b - - 0 1")

    assert chess.A8 in squares_in_danger(board)


def test_starting_position_has_no_danger() -> None:
    assert squares_in_danger(chess.Board()) == frozenset()


def test_contested_margins_show_only_squares_both_sides_attack() -> None:
    # White: Rd1 and Nc3 both hit d5; Black: only the e6 pawn does.
    board = chess.Board("k7/8/4p3/8/8/2N5/8/3R3K w - - 0 1")

    margins = contested_square_margins(board)

    assert margins[chess.D5] == 1
    # d2 is attacked by White alone, so it stays untinted.
    assert chess.D2 not in margins


def test_contested_margins_omit_evenly_contested_squares() -> None:
    # Both queens attack d4 in this mirrored setup; the margin cancels.
    board = chess.Board("3q3k/8/8/8/3p4/8/8/3Q3K w - - 0 1")

    assert chess.D4 not in contested_square_margins(board)


def test_starting_position_has_no_contested_squares() -> None:
    # No contact yet: the overlay stays clean instead of tinting both camps.
    assert contested_square_margins(chess.Board()) == {}
