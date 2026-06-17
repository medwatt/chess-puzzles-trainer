from __future__ import annotations

import random

import chess

from chess_puzzles.vision import analysis
from chess_puzzles.vision.analysis import ColorScope
from chess_puzzles.vision.drills.captures import CapturesDrill
from chess_puzzles.vision.drills.long_range import LongRangeAttackDrill


def _squares(names: str) -> set[int]:
    return {chess.parse_square(n) for n in names.split()} if names else set()


def test_loose_pieces_excludes_kings_and_pawns_by_default() -> None:
    # White Bc4 has no defender; both side rooks in the corners are loose too.
    board = chess.Board("rnbqkb1r/pppp1ppp/5n2/4p3/2B1P3/8/PPPP1PPP/RNBQK1NR w KQkq - 0 1")
    result = analysis.loose_pieces(board)
    assert chess.C4 in result
    # kings never appear
    assert chess.E1 not in result and chess.E8 not in result
    # no pawns by default
    assert all(board.piece_at(sq).piece_type != chess.PAWN for sq in result)


def test_loose_pieces_scope_side_to_move() -> None:
    board = chess.Board("rnbqkb1r/pppp1ppp/5n2/4p3/2B1P3/8/PPPP1PPP/RNBQK1NR w KQkq - 0 1")
    only_white = analysis.loose_pieces(board, scope=ColorScope.SIDE_TO_MOVE)
    assert all(board.piece_at(sq).color == chess.WHITE for sq in only_white)


def test_loose_pieces_includes_equal_attack_and_defense_when_exchange_wins() -> None:
    board = chess.Board("4k3/8/8/3r4/8/8/3R4/4K3 w - - 0 1")
    assert chess.D5 in analysis.loose_pieces(board, scope=ColorScope.OPPONENT)


def test_loose_pieces_excludes_overdefended_piece() -> None:
    board = chess.Board("4k3/8/4b3/3r4/5n2/8/3R4/4K3 w - - 0 1")
    assert chess.D5 not in analysis.loose_pieces(board, scope=ColorScope.OPPONENT)


def test_loose_pieces_includes_hanging_xray_exchange() -> None:
    # Bf6 has one direct attacker and one direct defender, but Rf1 x-rays the
    # exchange after Rxf6 Rxf6, so the bishop is still won.
    board = chess.Board("5r2/4r2k/p4b1p/2PP1Rp1/3p4/6P1/P5PP/5RK1 w - - 0 1")
    assert chess.F6 in analysis.loose_pieces(board, scope=ColorScope.OPPONENT)


def test_loose_pieces_excludes_attacked_piece_when_exchange_loses() -> None:
    board = chess.Board("4rrk1/R6R/3p2p1/1N1P1p1n/2P5/1P3QPP/5PK1/2q5 w - - 0 1")
    assert chess.H5 not in analysis.loose_pieces(board, scope=ColorScope.OPPONENT)
    assert chess.C1 in analysis.loose_pieces(board, scope=ColorScope.OPPONENT)


def test_loose_pieces_ignores_illegal_attackers_while_in_check() -> None:
    # Black attacks Bd2 geometrically, but is in check and neither capture on d2
    # is legal, so direct pressure does not make the bishop loose.
    board = chess.Board("5rk1/5B1p/5PpP/2p2Q2/3pP3/1n1P1P2/1q1B4/3K4 b - - 0 1")
    assert chess.D2 not in analysis.loose_pieces(board, scope=ColorScope.OPPONENT)


def test_piece_pressure_reports_legal_attackers_and_defenders() -> None:
    board = chess.Board("5r2/4r2k/p4b1p/2PP1Rp1/3p4/6P1/P5PP/5RK1 w - - 0 1")
    pressure = analysis.piece_pressure(board, chess.F6)
    assert pressure.piece == chess.Piece(chess.BISHOP, chess.BLACK)
    assert pressure.attackers == frozenset({chess.F5})
    assert pressure.defenders == frozenset({chess.F8})
    assert analysis.is_loose(board, chess.F6)
    assert analysis.is_hanging(board, chess.F6)


def test_hanging_is_capturable_for_material_gain() -> None:
    # Rd2 attacks the loose black knight on d4.
    board = chess.Board("4k3/8/8/8/3n4/8/3R4/4K3 w - - 0 1")
    assert analysis.hanging_pieces(board) == frozenset({chess.D4})
    # A knight that is loose but unattacked is not hanging.
    quiet = chess.Board("4k3/8/8/3n4/8/8/4R3/4K3 w - - 0 1")
    assert analysis.hanging_pieces(quiet) == frozenset()


def test_hanging_ignores_pinned_attackers() -> None:
    board = chess.Board("r4rk1/1p2p1bp/nq1pP2B/p1p5/2P1b1Q1/2N5/PP3PPP/R3K2R b KQ - 0 1")
    assert chess.H6 not in analysis.hanging_pieces(board)


def test_hanging_ignores_captures_that_are_recaptured() -> None:
    board = chess.Board("2r1k1nr/pp1b2pp/4p3/3pp2B/8/1P6/PNqQ1PPP/R4RK1 b - - 0 1")
    assert chess.B2 not in analysis.hanging_pieces(board)


def test_hanging_includes_favorable_captures_even_when_recaptured() -> None:
    board = chess.Board("k7/8/8/2p5/3Q4/8/8/3R3K b - - 0 1")
    assert chess.D4 in analysis.hanging_pieces(board)


def test_hanging_static_exchange_follows_longer_capture_chain() -> None:
    board = chess.Board("4k3/8/8/3r4/8/3n4/3R4/3R1K2 b - - 0 1")
    assert chess.D2 not in analysis.hanging_pieces(board)


def test_capturable_defaults_to_opponent_pieces_including_pawns() -> None:
    board = chess.Board("4k3/8/8/3np3/2PP4/8/3R4/4K3 w - - 0 1")
    assert analysis.capturable_pieces(board) == _squares("d5 e5")


def test_capturable_scope_side_to_move_and_both() -> None:
    board = chess.Board("4k3/8/8/3np3/2PP4/8/3R4/4K3 w - - 0 1")
    assert analysis.capturable_pieces(board, scope=ColorScope.SIDE_TO_MOVE) == _squares("d4")
    assert analysis.capturable_pieces(board, scope=ColorScope.BOTH) == _squares("d4 d5 e5")


def test_capturable_can_exclude_pawns() -> None:
    board = chess.Board("4k3/8/8/3np3/2PP4/8/3R4/4K3 w - - 0 1")
    assert analysis.capturable_pieces(board, include_pawns=False) == _squares("d5")


def test_capturable_ignores_en_passant() -> None:
    board = chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
    assert board.has_legal_en_passant()
    assert analysis.capturable_pieces(board) == frozenset()


def test_capturable_ignores_pinned_attackers() -> None:
    board = chess.Board("4r2k/8/8/7n/8/8/4B3/4K3 w - - 0 1")
    assert analysis.capturable_pieces(board) == frozenset()


def test_captures_drill_defaults_to_opponent_targets() -> None:
    drill = CapturesDrill()
    board = chess.Board("4k3/8/8/3np3/2PP4/8/3R4/4K3 w - - 0 1")
    question = drill.make_question(board, random.Random(0))
    assert drill.name == "Available captures"
    assert question.prompt == "Click capturable pieces"
    assert question.answer == _squares("d5 e5")


def test_reach_pawn_diagonals_and_blocker_inclusion() -> None:
    board = chess.Board("4k3/8/8/3p4/8/8/3R4/4K3 b - - 0 1")
    assert analysis.piece_reach(board, chess.D5) == _squares("c4 e4")  # black pawn: diagonals only
    rook = analysis.piece_reach(board, chess.D2)
    assert chess.D5 in rook and chess.D6 not in rook  # stops at and includes the first blocker


def test_reach_excludes_own_pieces_when_requested() -> None:
    board = chess.Board("4k3/8/8/8/8/8/3PR3/4K3 w - - 0 1")  # Re2 defends Pd2 and Ke1
    full = analysis.piece_reach(board, chess.E2)
    trimmed = analysis.piece_reach(board, chess.E2, include_defended_squares=False)
    assert chess.D2 in full and chess.E1 in full
    assert chess.D2 not in trimmed and chess.E1 not in trimmed


def test_long_range_attackers_clicks_sliders_with_enemy_piece_targets() -> None:
    board = chess.Board("n3k3/8/8/8/8/3n4/8/R2Q1BK1 w Q - 0 1")
    result = analysis.long_range_attackers(board)
    assert result == _squares("a1 d1 f1")


def test_long_range_attackers_ignores_friendly_and_pawn_targets_by_default() -> None:
    board = chess.Board("p3k3/8/8/8/8/3p4/8/R2Q1BK1 w Q - 0 1")
    assert analysis.long_range_attackers(board) == frozenset()
    assert analysis.long_range_attackers(board, include_pawns=True) == _squares("a1 d1 f1")


def test_long_range_attackers_ignores_adjacent_enemy_targets() -> None:
    adjacent = chess.Board("k7/8/6Qb/8/8/8/8/4K3 w - - 0 1")
    assert chess.G6 not in analysis.long_range_attackers(adjacent)
    distant = chess.Board("k7/8/4b1Q1/8/8/8/8/4K3 w - - 0 1")
    assert analysis.long_range_attackers(distant) == _squares("g6")


def test_long_range_attackers_scope() -> None:
    board = chess.Board("n3k3/8/8/8/8/3n4/8/R2Q1BK1 w Q - 0 1")
    assert analysis.long_range_attackers(board, scope=ColorScope.SIDE_TO_MOVE) == _squares("a1 d1 f1")
    assert analysis.long_range_attackers(board, scope=ColorScope.OPPONENT) == frozenset()


def test_long_range_drill_defaults_to_side_to_move_attackers() -> None:
    drill = LongRangeAttackDrill()
    board = chess.Board("n3k3/8/8/8/8/3n4/8/R2Q1BK1 w Q - 0 1")
    question = drill.make_question(board, random.Random(0))
    assert drill.name == "Long-range attacks"
    assert question.prompt == "Click long-range attackers"
    assert question.answer == _squares("a1 d1 f1")


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
    rook = analysis.piece_reach(board, chess.A1)
    assert chess.D1 in rook and chess.E1 not in rook
