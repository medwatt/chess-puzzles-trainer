from __future__ import annotations

import random

import chess

from chess_puzzles.vision import analysis
from chess_puzzles.vision.analysis import ColorScope
from chess_puzzles.vision.drills.captures import CapturesDrill
from chess_puzzles.vision.drills.long_range import LongRangeAttackDrill
from chess_puzzles.vision.drills.loose import LooseDrill


def _squares(names: str) -> set[int]:
    return {chess.parse_square(n) for n in names.split()} if names else set()


def test_loose_pieces_excludes_kings_and_pawns_by_default() -> None:
    # Bc4 has no attacker and no defender (0 vs 0) -> loose; kings/pawns excluded.
    board = chess.Board("rnbqkb1r/pppp1ppp/5n2/4p3/2B1P3/8/PPPP1PPP/RNBQK1NR w KQkq - 0 1")
    result = analysis.loose_pieces(board)
    assert chess.C4 in result
    assert chess.E1 not in result and chess.E8 not in result
    assert all(board.piece_at(sq).piece_type != chess.PAWN for sq in result)


def test_loose_pieces_scope_side_to_move() -> None:
    board = chess.Board("rnbqkb1r/pppp1ppp/5n2/4p3/2B1P3/8/PPPP1PPP/RNBQK1NR w KQkq - 0 1")
    only_white = analysis.loose_pieces(board, scope=ColorScope.SIDE_TO_MOVE)
    assert all(board.piece_at(sq).color == chess.WHITE for sq in only_white)


def test_loose_is_equal_attackers_and_defenders() -> None:
    # Bishop c3: one attacker (Rc1) and one defender (Qb4) -> loose (1 vs 1).
    board = chess.Board("r6k/1pB2p1p/p5p1/8/Pq3P2/1Pb3P1/6QP/2R4K w - - 0 1")
    assert analysis.pressure_counts(board, chess.C3) == (1, 1)
    assert analysis.is_loose(board, chess.C3)
    assert not analysis.is_hanging(board, chess.C3)


def test_loose_excludes_over_defended_and_more_attacked() -> None:
    # d5 rook: one attacker, two defenders -> over-defended, neither loose nor hanging.
    board = chess.Board("4k3/8/4b3/3r4/5n2/8/3R4/4K3 w - - 0 1")
    assert analysis.pressure_counts(board, chess.D5) == (1, 2)
    assert not analysis.is_loose(board, chess.D5)
    assert not analysis.is_hanging(board, chess.D5)
    # d4 knight: one attacker, no defender -> hanging (1 vs 0), not loose.
    board = chess.Board("4k3/8/8/8/3n4/8/3R4/4K3 w - - 0 1")
    assert analysis.is_hanging(board, chess.D4)
    assert not analysis.is_loose(board, chess.D4)


def test_loose_drill_skips_positions_with_a_hanging_piece() -> None:
    drill = LooseDrill()  # scope OPPONENT
    # Black has a loose bishop (Bc6: Ba4 vs b7 pawn) and a hanging knight (Ng4: Rg1,
    # no defender). The hanging piece would be a confusing distractor, so skip it.
    mixed = chess.Board("4k3/1p6/2b5/8/B5n1/8/8/4K1R1 w - - 0 1")
    assert analysis.loose_pieces(mixed, scope=ColorScope.OPPONENT) == _squares("c6")
    assert analysis.hanging_pieces(mixed, scope=ColorScope.OPPONENT) == _squares("g4")
    assert not drill.accepts(mixed)
    # Remove the knight: now only a balanced piece remains, so the position is served.
    clean = chess.Board("4k3/1p6/2b5/8/B7/8/8/4K3 w - - 0 1")
    assert drill.accepts(clean)
    assert drill._answer(clean) == _squares("c6")


def test_contested_only_drops_untouched_pieces() -> None:
    board = chess.Board("r6k/8/8/8/8/8/8/4K3 w - - 0 1")  # a8 rook: 0 vs 0
    assert chess.A8 in analysis.loose_pieces(board)
    assert chess.A8 not in analysis.loose_pieces(board, contested_only=True)


def test_pressure_counts_includes_xray_battery() -> None:
    # Rf1 X-rays the f-file behind Rf5: bishop f6 has two attackers, one defender.
    board = chess.Board("5r2/4r2k/p4b1p/2PP1Rp1/3p4/6P1/P5PP/5RK1 w - - 0 1")
    assert analysis.pressure_counts(board, chess.F6) == (2, 1)
    assert analysis.is_hanging(board, chess.F6)
    assert not analysis.is_loose(board, chess.F6)


def test_pressure_discounts_pinned_attacker() -> None:
    # The only attacker of d5 (Rd3) is pinned along rank 3 and cannot reach it.
    board = chess.Board("4k3/8/8/3n4/8/K2R3r/8/8 w - - 0 1")
    assert analysis.pressure(board, chess.D5, chess.WHITE) == frozenset()
    assert not analysis.is_hanging(board, chess.D5)


def test_counts_classify_a_full_position() -> None:
    # Only c7 has more attackers than defenders (hanging); d8, e7, c1 and b5 are
    # balanced (loose).
    board = chess.Board("3r2k1/p1rbnpbp/1p2p1p1/1N6/1P1N4/4PB2/P4PPP/2RR2K1 b - - 1 1")
    assert analysis.hanging_pieces(board) == frozenset({chess.C7})
    loose = analysis.loose_pieces(board)
    assert {chess.D8, chess.E7, chess.C1, chess.B5} <= loose
    assert chess.C7 not in loose


def test_pressure_counts_xray_examples() -> None:
    # f1 rook is loose at 2 vs 2 (a6 bishop X-rays through the c4 queen).
    board = chess.Board("2r1r1k1/p1p4p/bp1p2pP/6P1/2q1P3/P1N2Q2/1PP5/1K1R1R2 b - - 0 1")
    assert analysis.pressure_counts(board, chess.F1) == (2, 2)
    assert analysis.is_loose(board, chess.F1)
    # d6 bishop is hanging at 2 vs 1 (g3 queen X-rays through the e5 queen).
    board = chess.Board("kn6/pp6/3b4/4q3/8/6Q1/PP3P2/KN1R4 w - - 0 1")
    assert analysis.pressure_counts(board, chess.D6) == (2, 1)
    assert analysis.is_hanging(board, chess.D6)


def test_hanging_is_more_attackers_than_defenders() -> None:
    board = chess.Board("4k3/8/8/8/3n4/8/3R4/4K3 w - - 0 1")
    assert analysis.hanging_pieces(board) == frozenset({chess.D4})
    quiet = chess.Board("4k3/8/8/3n4/8/8/4R3/4K3 w - - 0 1")
    assert analysis.hanging_pieces(quiet) == frozenset()


def test_hanging_ignores_pinned_attackers() -> None:
    board = chess.Board("r4rk1/1p2p1bp/nq1pP2B/p1p5/2P1b1Q1/2N5/PP3PPP/R3K2R b KQ - 0 1")
    assert chess.H6 not in analysis.hanging_pieces(board)


def test_winnable_only_drops_value_losing_hanging() -> None:
    # Knight d5 is defended by the c6 pawn but attacked by Qa2 and Rd1: 2 vs 1, so
    # it is hanging by count -- yet capturing loses material, so it is not winnable
    # and the drill should not serve it.
    board = chess.Board("4k3/8/2p5/3n4/8/8/Q7/3R1K2 w - - 0 1")
    assert analysis.pressure_counts(board, chess.D5) == (2, 1)
    assert analysis.is_hanging(board, chess.D5)
    assert not analysis.is_winnable(board, chess.D5)
    assert chess.D5 in analysis.hanging_pieces(board, scope=ColorScope.OPPONENT)
    assert chess.D5 not in analysis.hanging_pieces(
        board, scope=ColorScope.OPPONENT, winnable_only=True
    )
    # A plain free capture is still both hanging and winnable.
    free = chess.Board("4k3/8/8/8/3n4/8/3R4/4K3 w - - 0 1")
    assert chess.D4 in analysis.hanging_pieces(free, winnable_only=True)


def test_attacker_in_check_only_counts_legal_captures() -> None:
    # White is in check from Bf2, so no attacker that fails to resolve the check
    # counts. Be5xf6 is illegal, Kxf2 walks into the f6 queen, and Qxf2 is met by
    # Qxf2 -- nothing is hanging. The f2 bishop is merely loose (Qd2 vs Qf6).
    board = chess.Board("rnb4r/pp1k4/2p1pqB1/3pB3/3Pp3/4P3/PPPQ1bP1/R3K2R w - - 0 1")
    assert board.is_check()
    assert analysis.hanging_pieces(board, scope=ColorScope.OPPONENT) == frozenset()
    assert analysis.is_loose(board, chess.F2)
    assert analysis.pressure_counts(board, chess.F2) == (1, 1)


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
