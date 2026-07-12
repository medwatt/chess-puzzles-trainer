"""Where a repertoire line should start drilling.

Course lines arrive in depth-first order -- whether split from one game's
variation tree or exported as consecutive sibling games -- so a line's
longest shared prefix with *all* earlier lines is its prefix with the
immediately preceding one. Drilling each line from that divergence point
makes a front-to-back pass cover every move of the course exactly once: no
shared trunk is re-typed per line, no move goes undrilled. Derived on demand
from stored moves; nothing is persisted.
"""

from __future__ import annotations

from chess_puzzles.puzzle.model import Puzzle


def drill_prefix_length(previous: Puzzle | None, current: Puzzle) -> int:
    """Plies of ``current`` already drilled by the preceding deck line.

    Any two consecutive lines from the same starting position share whatever
    opening moves they have in common -- the user just played them. Different
    start positions (study-page FENs, first line of a deck) start from the
    beginning, and so does a line identical to (or fully contained in) its
    predecessor: a prefix must leave something to drill.
    """
    if previous is None or previous.initial_fen != current.initial_fen:
        return 0
    shared = 0
    for earlier, later in zip(previous.moves, current.moves):
        if earlier != later:
            break
        shared += 1
    return shared if shared < len(current.moves) else 0
