from __future__ import annotations

import chess


def infer_skip_first_move(
    initial_fen: str, moves: tuple[chess.Move, ...], player_color: chess.Color | None
) -> bool:
    """Decide whether the opponent plays the first move (user solves from move 2).

    Exact when the player's side is known: skip iff the side to move in the FEN
    is NOT the user's side. Otherwise fall back to the parity heuristic, which
    assumes the puzzle ends on the user's move: an even number of solution moves
    means the user moved second (skip). A move-free study page never skips.
    """
    if not moves:
        return False
    if player_color is not None:
        return chess.Board(initial_fen).turn != player_color
    return len(moves) % 2 == 0
