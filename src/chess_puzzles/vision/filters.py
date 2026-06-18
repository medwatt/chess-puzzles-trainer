"""Position filters and the combinators that compose them.

A filter is just a predicate over a board (``Accepts``); drills supply their own
positive filter via ``Drill.accepts``. This module is the home for the
*cross-cutting* rules that wrap any drill's filter, so the drill-agnostic
``VisionSession`` composes policy here rather than defining chess rules itself.
"""

from __future__ import annotations

from collections.abc import Callable

import chess

Accepts = Callable[[chess.Board], bool]


def not_in_check(accepts: Accepts) -> Accepts:
    """Wrap a filter so it also rejects positions with the side to move in check.

    A position where the side to move is in check distorts the attacker/defender
    counts the drills rely on (only check-resolving captures are legal) and is
    jarring to be shown in a calm perception drill, so no drill is served one.
    """
    return lambda board: not board.is_check() and accepts(board)
