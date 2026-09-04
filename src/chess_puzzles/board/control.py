"""Fast heuristic to find pieces under pressure.

We count attackers and defenders on each square but skip pins and
capture sequences. The goal is to highlight pieces you should look at
twice, not to compute the exact evaluation of the position.

Deliberately *not* the same question as ``vision.analysis``: the drills ask
whether a piece can actually be won (a full static exchange), while this asks
whether a piece looks worth a second glance. A piece can be under pressure here
and perfectly safe there. Keep the two vocabularies apart -- calling both
"hanging" is what made them look like a contradiction rather than two
intentionally different tools.
"""

from __future__ import annotations

from enum import Enum

import chess

from chess_puzzles.move_utils import PIECE_VALUES


class ControlOverlayMode(Enum):
    """What the on-demand insight overlay currently shows."""

    OFF = "off"
    UNDER_PRESSURE = "under_pressure"
    CONTROL = "control"


def squares_in_danger(board: chess.Board) -> frozenset[int]:
    """Return squares whose occupant piece looks vulnerable.

    A square is flagged if:
    - The occupant is a king and is attacked (always flagged).
    - The piece has more attackers than defenders.
    - The piece is attacked by something cheaper than itself (e.g. a
      pawn attacking a defended queen).

    Pins are ignored: an absolutely pinned piece still counts as a
    defender.
    """
    danger: set[int] = set()
    for square, piece in board.piece_map().items():
        attackers = board.attackers(not piece.color, square)
        if not attackers:
            continue
        # Criterion 1: an attacked king is always in danger.
        if piece.piece_type == chess.KING:
            danger.add(square)
            continue
        # Criterion 2: more attackers than defenders.
        defenders = board.attackers(piece.color, square)
        if len(attackers) > len(defenders):
            danger.add(square)
            continue
        # Criterion 3: attacked by something cheaper (pawn hitting queen,
        # even if the queen is defended).
        cheapest_attacker = min(
            PIECE_VALUES[board.piece_type_at(attacker_square) or chess.PAWN]
            for attacker_square in attackers
        )
        if cheapest_attacker < PIECE_VALUES[piece.piece_type]:
            danger.add(square)
    return frozenset(danger)


def contested_square_margins(board: chess.Board) -> dict[int, int]:
    """Squares where both sides attack, keyed by White minus Black attackers.

    Squares attacked by only one side are skipped (colouring each side's
    own territory makes it harder to spot the contested ones). Evenly
    contested squares (margin of zero) are also skipped.

    The counts are raw attacker numbers. Batteries blocked by pieces are
    not unfolded into separate attackers.
    """
    margins: dict[int, int] = {}
    for square in chess.SQUARES:
        white = len(board.attackers(chess.WHITE, square))
        if not white:
            continue
        black = len(board.attackers(chess.BLACK, square))
        if not black:
            continue
        margin = white - black
        if margin != 0:
            margins[square] = margin
    return margins
