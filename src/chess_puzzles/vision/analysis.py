"""Pure ground-truth computations for board vision drills.

Every function takes a ``chess.Board`` and returns a ``frozenset`` of square
indices -- the set of squares that count as a correct answer. They have no UI
or randomness, so each one is directly unit-testable from a FEN. The drills in
``vision/drills/`` are thin wrappers that call these and add prompt text.
"""

from __future__ import annotations

from collections.abc import Iterable
from enum import Enum

import chess


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


def undefended(
    board: chess.Board,
    *,
    scope: ColorScope = ColorScope.BOTH,
    include_pawns: bool = False,
) -> frozenset[int]:
    """Pieces with zero friendly defenders on their square (kings excluded)."""
    colors = scope_colors(board, scope)
    result: set[int] = set()
    for square, piece in board.piece_map().items():
        if piece.color not in colors:
            continue
        if not _is_candidate(piece, include_pawns):
            continue
        if not board.attackers(piece.color, square):
            result.add(square)
    return frozenset(result)


def hanging(
    board: chess.Board,
    *,
    scope: ColorScope = ColorScope.BOTH,
    include_pawns: bool = False,
) -> frozenset[int]:
    """Undefended *and* attacked by at least one enemy piece (kings excluded).

    This is the strict literal definition, deliberately distinct from
    ``board.control.squares_in_danger`` which uses a looser danger heuristic.
    """
    colors = scope_colors(board, scope)
    result: set[int] = set()
    for square, piece in board.piece_map().items():
        if piece.color not in colors:
            continue
        if not _is_candidate(piece, include_pawns):
            continue
        if board.attackers(piece.color, square):
            continue
        if board.attackers(not piece.color, square):
            result.add(square)
    return frozenset(result)


def reach(
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


def pieces_of_types(board: chess.Board, piece_types: Iterable[chess.PieceType]) -> list[int]:
    """Squares holding any of ``piece_types`` (either color). Used by reach drills."""
    wanted = set(piece_types)
    return [square for square, piece in board.piece_map().items() if piece.piece_type in wanted]
