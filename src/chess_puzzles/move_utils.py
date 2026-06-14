from __future__ import annotations

import chess


def normalize_promotion(
    board: chess.Board,
    move: chess.Move,
    expected_move: chess.Move | None = None,
) -> chess.Move:
    """Fill in a missing promotion piece for GUI-originated moves."""

    if move.promotion is not None:
        return move

    piece = board.piece_at(move.from_square)
    if piece is None or piece.piece_type != chess.PAWN:
        return move

    target_rank = chess.square_rank(move.to_square)
    if target_rank not in (0, 7):
        return move

    if expected_move and expected_move.from_square == move.from_square and expected_move.to_square == move.to_square:
        return expected_move

    return chess.Move(move.from_square, move.to_square, promotion=chess.QUEEN)
