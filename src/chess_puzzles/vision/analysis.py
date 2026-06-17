"""Pure ground-truth computations for board vision drills.

This module owns the chess logic behind the drills: pressure on a piece,
same-square exchanges, checking moves, reach, and answer sets. It has no UI or
randomness, so each concept is directly unit-testable from a FEN. The drills in
``vision/drills/`` stay thin wrappers that call these functions and add prompt
text.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum

import chess

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


@dataclass(frozen=True, slots=True)
class PiecePressure:
    """Direct pressure on one occupied square."""

    square: int
    piece: chess.Piece | None
    attackers: frozenset[int]
    defenders: frozenset[int]


def piece_pressure(board: chess.Board, square: int) -> PiecePressure:
    """Legal enemy attackers and direct friendly defenders of a piece."""
    piece = board.piece_at(square)
    if piece is None:
        return PiecePressure(square, None, frozenset(), frozenset())
    return PiecePressure(
        square=square,
        piece=piece,
        attackers=frozenset(_legal_attackers(board, not piece.color, square)),
        defenders=frozenset(board.attackers(piece.color, square)),
    )


def is_hanging(board: chess.Board, square: int) -> bool:
    """Whether the piece on ``square`` can be won by a legal capture sequence."""
    piece = board.piece_at(square)
    if piece is None or piece.piece_type == chess.KING:
        return False
    return _can_be_won_by_capture(board, square, piece)


def is_loose(board: chess.Board, square: int) -> bool:
    """Whether the piece on ``square`` is not safely protected."""
    pressure = piece_pressure(board, square)
    piece = pressure.piece
    if piece is None or piece.piece_type == chess.KING:
        return False
    if not pressure.defenders:
        return True
    return is_hanging(board, square)


def loose_pieces(
    board: chess.Board,
    *,
    scope: ColorScope = ColorScope.BOTH,
    include_pawns: bool = False,
) -> frozenset[int]:
    """Pieces that are not safely protected on their square.

    This is the broad "loose piece" scan used by the board-vision drill:
    pieces with no defenders, and pieces that can be won by a same-square
    exchange.
    """
    colors = scope_colors(board, scope)
    result: set[int] = set()
    for square, piece in board.piece_map().items():
        if piece.color not in colors:
            continue
        if not _is_candidate(piece, include_pawns):
            continue
        if is_loose(board, square):
            result.add(square)
    return frozenset(result)


def hanging_pieces(
    board: chess.Board,
    *,
    scope: ColorScope = ColorScope.BOTH,
    include_pawns: bool = False,
) -> frozenset[int]:
    """Pieces an enemy can legally capture for material gain.

    This uses a small static exchange evaluator on the target square. It is
    still engine-free, but handles pinned pieces and longer recapture chains.
    """
    colors = scope_colors(board, scope)
    result: set[int] = set()
    for square, piece in board.piece_map().items():
        if piece.color not in colors:
            continue
        if not _is_candidate(piece, include_pawns):
            continue
        if is_hanging(board, square):
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


def _can_be_won_by_capture(board: chess.Board, square: int, piece: chess.Piece) -> bool:
    enemy = not piece.color
    captured_value = _PIECE_VALUES[piece.piece_type]
    for attacker_square in _legal_attackers(board, enemy, square):
        move = chess.Move(attacker_square, square)
        test = _with_turn(board, enemy)
        test.push(move)
        if captured_value - _best_exchange_gain(test, square) > 0:
            return True
    return False


def _legal_attackers(board: chess.Board, color: chess.Color, square: int) -> chess.SquareSet:
    test = _with_turn(board, color)
    return chess.SquareSet(
        attacker_square
        for attacker_square in board.attackers(color, square)
        if test.is_legal(chess.Move(attacker_square, square))
    )


def _with_turn(board: chess.Board, turn: chess.Color) -> chess.Board:
    test = board.copy(stack=False)
    test.turn = turn
    return test


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


def _best_exchange_gain(board: chess.Board, square: int) -> int:
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


def pieces_of_types(board: chess.Board, piece_types: Iterable[chess.PieceType]) -> list[int]:
    """Squares holding any of ``piece_types`` (either color). Used by reach drills."""
    wanted = set(piece_types)
    return [square for square, piece in board.piece_map().items() if piece.piece_type in wanted]
