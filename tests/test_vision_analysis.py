from __future__ import annotations

import chess

from chess_puzzles.vision import analysis
from chess_puzzles.vision.analysis import ColorScope


def _squares(names: str) -> set[int]:
    return {chess.parse_square(n) for n in names.split()} if names else set()


def test_undefended_excludes_kings_and_pawns_by_default() -> None:
    # White Bc4 has no defender; both side rooks in the corners are undefended too.
    board = chess.Board("rnbqkb1r/pppp1ppp/5n2/4p3/2B1P3/8/PPPP1PPP/RNBQK1NR w KQkq - 0 1")
    result = analysis.undefended(board)
    assert chess.C4 in result
    # kings never appear
    assert chess.E1 not in result and chess.E8 not in result
    # no pawns by default
    assert all(board.piece_at(sq).piece_type != chess.PAWN for sq in result)


def test_undefended_scope_side_to_move() -> None:
    board = chess.Board("rnbqkb1r/pppp1ppp/5n2/4p3/2B1P3/8/PPPP1PPP/RNBQK1NR w KQkq - 0 1")
    only_white = analysis.undefended(board, scope=ColorScope.SIDE_TO_MOVE)
    assert all(board.piece_at(sq).color == chess.WHITE for sq in only_white)


def test_hanging_is_undefended_and_attacked() -> None:
    # Rd2 attacks the undefended black knight on d4.
    board = chess.Board("4k3/8/8/8/3n4/8/3R4/4K3 w - - 0 1")
    assert analysis.hanging(board) == frozenset({chess.D4})
    # A knight that is undefended but unattacked is not hanging.
    quiet = chess.Board("4k3/8/8/3n4/8/8/4R3/4K3 w - - 0 1")
    assert analysis.hanging(quiet) == frozenset()


def test_reach_pawn_diagonals_and_blocker_inclusion() -> None:
    board = chess.Board("4k3/8/8/3p4/8/8/3R4/4K3 b - - 0 1")
    assert analysis.reach(board, chess.D5) == _squares("c4 e4")  # black pawn: diagonals only
    rook = analysis.reach(board, chess.D2)
    assert chess.D5 in rook and chess.D6 not in rook  # stops at and includes the first blocker


def test_reach_excludes_own_pieces_when_requested() -> None:
    board = chess.Board("4k3/8/8/8/8/8/3PR3/4K3 w - - 0 1")  # Re2 defends Pd2 and Ke1
    full = analysis.reach(board, chess.E2)
    trimmed = analysis.reach(board, chess.E2, include_defended_squares=False)
    assert chess.D2 in full and chess.E1 in full
    assert chess.D2 not in trimmed and chess.E1 not in trimmed


def test_king_zone_only_attacked_neighbours() -> None:
    board = chess.Board("4k3/8/8/8/8/8/4R3/4K3 w - - 0 1")  # Re2 controls the e-file
    assert analysis.king_zone_attacked(board, chess.BLACK) == frozenset({chess.E7})


def test_attackers_of_piece_excludes_friendly_defenders() -> None:
    # Black knight d4: white Rd2 attacks it (counts); black Bf6 defends it (excluded).
    board = chess.Board("4k3/8/5b2/8/3n4/8/3R4/4K3 w - - 0 1")
    assert analysis.attackers_of_piece(board, chess.D4) == _squares("d2")
    # An empty square has no owner and so no attackers.
    assert analysis.attackers_of_piece(board, chess.A8) == frozenset()


def test_checking_destinations() -> None:
    # White rook h5, black king e8: Rh8 checks on the 8th rank, Re5 checks up the
    # e-file; a quiet Ra5 does not.
    board = chess.Board("4k3/8/8/7R/8/8/8/4K3 w - - 0 1")
    dests = analysis.checking_destinations(board)
    assert chess.H8 in dests and chess.E5 in dests
    assert chess.A5 not in dests
    # A position with no check available yields the empty set.
    quiet = chess.Board("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
    assert analysis.checking_destinations(quiet) == frozenset()


def test_reach_is_blocked_by_the_king() -> None:
    board = chess.Board("8/8/8/8/8/8/8/R2K3r w - - 0 1")
    # White Ra1 is blocked by its own king on d1 before reaching the far side.
    rook = analysis.reach(board, chess.A1)
    assert chess.D1 in rook and chess.E1 not in rook
