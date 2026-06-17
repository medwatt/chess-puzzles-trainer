"""Pure ground-truth computations for board vision drills.

This module owns the chess logic behind the drills: pressure on a piece,
same-square exchanges, checking moves, reach, and answer sets. It has no UI or
randomness, so each concept is directly unit-testable from a FEN. The drills in
``vision/drills/`` stay thin wrappers that call these functions and add prompt
text.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum

import chess

# Step deltas (file, rank) for sliding rays, split by the piece types that move
# along them. Used to count X-ray / battery pressure through aligned sliders.
_STRAIGHT_STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))
_DIAGONAL_STEPS = ((1, 1), (1, -1), (-1, 1), (-1, -1))

# Rough piece values, used only by the winnability check that filters which
# count-hanging pieces the hanging drill actually serves (not by the count rule).
_PIECE_VALUES: dict[chess.PieceType, int] = {
    chess.PAWN: 1,
    chess.KNIGHT: 3,
    chess.BISHOP: 3,
    chess.ROOK: 5,
    chess.QUEEN: 9,
    chess.KING: 100,
}


class ColorScope(Enum):
    """Whose pieces an answer set should include."""

    BOTH = "both"
    SIDE_TO_MOVE = "side_to_move"
    OPPONENT = "opponent"


def scope_colors(board: chess.Board, scope: ColorScope) -> tuple[chess.Color, ...]:
    if scope is ColorScope.BOTH:
        return (chess.WHITE, chess.BLACK)
    if scope is ColorScope.SIDE_TO_MOVE:
        return (board.turn,)
    return (not board.turn,)


def pressure(board: chess.Board, square: int, color: chess.Color) -> frozenset[int]:
    """``color`` pieces bearing on ``square`` -- direct attackers/defenders plus
    indirect X-ray/battery pieces along the same line, minus any piece that could
    not actually move onto the square (pinned, or unable to act because its own
    king is in check).

    This is the counting primitive the loose/hanging drills are built on: count
    attackers and defenders, include X-rays, and discount pieces that cannot move.
    """
    target = board.piece_at(square)
    if target is not None and color != target.color and color == board.turn and board.is_check():
        # The attacking side is in check: its only legal move is one that resolves
        # the check, so a piece bears on the square only if capturing there is
        # actually legal right now (an X-ray piece can never be that move).
        return frozenset(
            sq for sq in board.attackers(color, square) if board.is_legal(chess.Move(sq, square))
        )
    candidates = set(board.attackers(color, square)) | _xray_sliders(board, square, color)
    return frozenset(sq for sq in candidates if _can_move_onto(board, sq, square))


def pressure_counts(board: chess.Board, square: int) -> tuple[int, int]:
    """``(attackers, defenders)`` on ``square`` under the same counting rules."""
    piece = board.piece_at(square)
    if piece is None:
        return (0, 0)
    return (
        len(pressure(board, square, not piece.color)),
        len(pressure(board, square, piece.color)),
    )


def is_hanging(board: chess.Board, square: int) -> bool:
    """Whether ``square`` has strictly more attackers than defenders.

    A pure count (X-ray-aware, pin-discounted): a piece that is more attacked than
    defended. Whether it can actually be won is a separate calculation the drill
    deliberately leaves out.
    """
    piece = board.piece_at(square)
    if piece is None or piece.piece_type == chess.KING:
        return False
    attackers, defenders = pressure_counts(board, square)
    return attackers > defenders


def is_loose(board: chess.Board, square: int) -> bool:
    """Whether ``square`` has equally many attackers and defenders.

    Balanced now, but one removed defender or one new attacker away from hanging.
    A piece with no pressure at all (0 vs 0) counts as loose too; the drill can
    filter those out via ``contested_only``.
    """
    piece = board.piece_at(square)
    if piece is None or piece.piece_type == chess.KING:
        return False
    attackers, defenders = pressure_counts(board, square)
    return attackers == defenders


def loose_pieces(
    board: chess.Board,
    *,
    scope: ColorScope = ColorScope.BOTH,
    include_pawns: bool = False,
    contested_only: bool = False,
) -> frozenset[int]:
    """Pieces with as many attackers as defenders.

    With ``contested_only`` the untouched pieces that have no attacker at all
    (0 vs 0) are dropped, leaving the genuinely contested targets.
    """
    colors = scope_colors(board, scope)
    result: set[int] = set()
    for square, piece in board.piece_map().items():
        if piece.color not in colors or not _is_candidate(piece, include_pawns):
            continue
        attackers, defenders = pressure_counts(board, square)
        if attackers != defenders or (contested_only and attackers == 0):
            continue
        result.add(square)
    return frozenset(result)


def is_winnable(board: chess.Board, square: int) -> bool:
    """Whether the piece on ``square`` can be won by a legal capture sequence.

    A value-aware static exchange (the full recapture search in
    ``_best_exchange_gain``): used only to filter which count-hanging pieces the
    drill actually serves, so the player is never shown a piece that is "hanging"
    by count yet cannot be taken (e.g. a knight defended by a pawn but attacked
    only by a queen and a rook).
    """
    piece = board.piece_at(square)
    if piece is None or piece.piece_type == chess.KING:
        return False
    enemy = not piece.color
    captured_value = _PIECE_VALUES[piece.piece_type]
    test = _with_turn(board, enemy)
    for attacker_square in board.attackers(enemy, square):
        move = chess.Move(attacker_square, square)
        if not test.is_legal(move):
            continue
        after = test.copy(stack=False)
        after.push(move)
        if captured_value - _best_exchange_gain(after, square) > 0:
            return True
    return False


def hanging_pieces(
    board: chess.Board,
    *,
    scope: ColorScope = ColorScope.BOTH,
    include_pawns: bool = False,
    winnable_only: bool = False,
) -> frozenset[int]:
    """Pieces with strictly more attackers than defenders.

    With ``winnable_only`` the result is narrowed to pieces that can actually be
    won by a capture sequence (``is_winnable``), dropping the count's value-losing
    false positives so the drill does not pose pieces the player cannot take.
    """
    colors = scope_colors(board, scope)
    result: set[int] = set()
    for square, piece in board.piece_map().items():
        if piece.color not in colors or not _is_candidate(piece, include_pawns):
            continue
        attackers, defenders = pressure_counts(board, square)
        if attackers > defenders and (not winnable_only or is_winnable(board, square)):
            result.add(square)
    return frozenset(result)


def capturable_pieces(
    board: chess.Board,
    *,
    scope: ColorScope = ColorScope.OPPONENT,
    include_pawns: bool = True,
) -> frozenset[int]:
    """Pieces that can be captured by the opposing side with a legal move.

    The returned squares are occupied target pieces, not the moving pieces.
    En passant is excluded because the captured pawn is not on the move's
    destination square and the right is not visible from a static diagram.
    """
    colors = scope_colors(board, scope)
    capture_targets = _legal_capture_targets_by({not color for color in colors}, board)
    result: set[int] = set()
    for target, piece in board.piece_map().items():
        if piece.color not in colors:
            continue
        if not _is_candidate(piece, include_pawns):
            continue
        if target in capture_targets:
            result.add(target)
    return frozenset(result)


def piece_reach(
    board: chess.Board,
    square: int,
    *,
    include_defended_squares: bool = True,
) -> frozenset[int]:
    """Squares the piece on ``square`` attacks (pawns: diagonals only).

    ``board.attacks`` already stops at and includes the first blocker. When
    ``include_defended_squares`` is False, squares occupied by the piece's own
    side are dropped, leaving only empty and capturable squares.
    """
    attacks = board.attacks(square)
    if include_defended_squares:
        return frozenset(attacks)
    piece = board.piece_at(square)
    if piece is None:
        return frozenset(attacks)
    return frozenset(s for s in attacks if board.color_at(s) != piece.color)


def long_range_attackers(
    board: chess.Board,
    *,
    scope: ColorScope = ColorScope.BOTH,
    include_pawns: bool = False,
) -> frozenset[int]:
    """Bishops, rooks, and queens attacking a non-adjacent enemy piece.

    The answer square is the sliding piece, not its target. Pawns are ignored by
    default so ordinary pawn captures do not dominate the drill. Adjacent pieces
    are ignored; the drill is about seeing longer rank/file/diagonal attacks.
    """
    return frozenset(long_range_attack_targets(board, scope=scope, include_pawns=include_pawns))


def long_range_attack_targets(
    board: chess.Board,
    *,
    scope: ColorScope = ColorScope.BOTH,
    include_pawns: bool = False,
) -> dict[int, frozenset[int]]:
    """Long-range attacking sliders keyed by the enemy pieces they directly see."""
    colors = scope_colors(board, scope)
    slider_types = {chess.BISHOP, chess.ROOK, chess.QUEEN}
    result: dict[int, set[int]] = {}
    for square, piece in board.piece_map().items():
        if piece.color not in colors or piece.piece_type not in slider_types:
            continue
        for target in board.attacks(square):
            target_piece = board.piece_at(target)
            if target_piece is None or target_piece.color == piece.color:
                continue
            if target_piece.piece_type == chess.PAWN and not include_pawns:
                continue
            if chess.square_distance(square, target) < 2:
                continue
            result.setdefault(square, set()).add(target)
    return {square: frozenset(targets) for square, targets in result.items()}


def king_zone_attacked(board: chess.Board, king_color: chess.Color) -> frozenset[int]:
    """Squares adjacent to ``king_color``'s king that the opponent attacks."""
    king_square = board.king(king_color)
    if king_square is None:
        return frozenset()
    enemy = not king_color
    ring = chess.SquareSet(chess.BB_KING_ATTACKS[king_square])
    return frozenset(s for s in ring if board.is_attacked_by(enemy, s))


def attackers_of_piece(board: chess.Board, square: int) -> frozenset[int]:
    """The enemy pieces that directly attack the piece standing on ``square``.

    The counting primitive behind captures: how many enemy pieces bear on a piece
    (against how many friendly pieces defend it) decides whether it can be won.
    Same-colour pieces are *defenders*, not attackers, so they are excluded; an
    empty square has no owner and so no attackers. X-ray / batteries are not
    included -- only pieces with a direct line.
    """
    piece = board.piece_at(square)
    if piece is None:
        return frozenset()
    return frozenset(board.attackers(not piece.color, square))


def checking_destinations(board: chess.Board) -> frozenset[int]:
    """Squares the side to move can land on to deliver check (including discoveries).

    The answer is the set of *destination* squares of legal checking moves, so a
    discovered check counts the square the unmasking piece moves to.
    """
    return frozenset(move.to_square for move in board.legal_moves if board.gives_check(move))


def _is_candidate(piece: chess.Piece, include_pawns: bool) -> bool:
    if piece.piece_type == chess.KING:
        return False
    if piece.piece_type == chess.PAWN and not include_pawns:
        return False
    return True


def _xray_sliders(board: chess.Board, square: int, color: chess.Color) -> set[int]:
    """``color`` sliders bearing on ``square`` along a rank/file/diagonal, seeing
    *through* aligned sliders (batteries and X-rays).

    A ray stays transparent only while the pieces on it are sliders that move
    along that ray (rook/queen on straights, bishop/queen on diagonals), of either
    colour -- a queen behind an enemy bishop on the same diagonal still bears on
    the square. Any other piece (knight, pawn, king, off-line slider) blocks the
    ray.
    """
    result: set[int] = set()
    file0, rank0 = chess.square_file(square), chess.square_rank(square)
    for steps, line_types in (
        (_STRAIGHT_STEPS, (chess.ROOK, chess.QUEEN)),
        (_DIAGONAL_STEPS, (chess.BISHOP, chess.QUEEN)),
    ):
        for dfile, drank in steps:
            file_, rank_ = file0 + dfile, rank0 + drank
            while 0 <= file_ < 8 and 0 <= rank_ < 8:
                sq = chess.square(file_, rank_)
                piece = board.piece_at(sq)
                if piece is not None:
                    if piece.piece_type not in line_types:
                        break
                    if piece.color == color:
                        result.add(sq)
                file_ += dfile
                rank_ += drank
    return result


def _can_move_onto(board: chess.Board, origin: int, target: int) -> bool:
    """Whether the piece on ``origin`` is free to move to ``target`` (not pinned away).

    A piece pinned to its king may only move along the pin line, so it cannot
    truly attack or defend a square off that line -- a pinned piece is a poor
    defender. Unpinned pieces (and the king) are always free here.
    """
    color = board.color_at(origin)
    if color is None:
        return False
    return target in board.pin(color, origin)


def _with_turn(board: chess.Board, turn: chess.Color) -> chess.Board:
    test = board.copy(stack=False)
    test.turn = turn
    return test


def _best_exchange_gain(board: chess.Board, square: int) -> int:
    """Best material the side to move can win from captures on ``square`` (>= 0).

    Recursive exchange search: at each ply the mover may capture (with any legal
    attacker) or stand pat at 0, so it follows the full recapture chain rather
    than stopping after one level.
    """
    captured = board.piece_at(square)
    if captured is None:
        return 0
    best = 0
    for attacker_square in board.attackers(board.turn, square):
        move = chess.Move(attacker_square, square)
        if not board.is_legal(move):
            continue
        test = board.copy(stack=False)
        test.push(move)
        gain = _PIECE_VALUES[captured.piece_type] - _best_exchange_gain(test, square)
        if gain > best:
            best = gain
    return best


def _legal_capture_targets_by(colors: set[chess.Color], board: chess.Board) -> set[int]:
    targets: set[int] = set()
    for color in colors:
        test = board.copy(stack=False)
        test.turn = color
        targets.update(
            move.to_square
            for move in test.legal_moves
            if test.is_capture(move) and not test.is_en_passant(move)
        )
    return targets


def pieces_of_types(board: chess.Board, piece_types: Iterable[chess.PieceType]) -> list[int]:
    """Squares holding any of ``piece_types`` (either color). Used by reach drills."""
    wanted = set(piece_types)
    return [square for square, piece in board.piece_map().items() if piece.piece_type in wanted]
