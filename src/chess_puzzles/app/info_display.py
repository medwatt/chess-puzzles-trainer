"""What the puzzle-info sidebar shows, per deck kind.

One declarative table instead of mode conditionals inside the widget code:
a new training mode states its row here and the sidebar follows. Fields that
would spoil an unsolved puzzle (the theme names the motif, the move counter
reveals the solution length) are hidden until the puzzle is complete when
``reveal_when_solved`` applies.
"""

from __future__ import annotations

from dataclasses import dataclass

from chess_puzzles.store import DECK_KIND_ARENA

# Shown in place of a field that is hidden until the puzzle is solved.
HIDDEN_TEXT = "?"


@dataclass(frozen=True, slots=True)
class InfoDisplay:
    show_deck_total: bool = True  # "3 / 50" -- meaningless in an endless deck
    show_rating: bool = False  # the session rating next to the position
    show_move_progress: bool = True  # move counter and progress bar
    show_theme: bool = True


def info_display_for(kind: str, *, complete: bool) -> InfoDisplay:
    if kind == DECK_KIND_ARENA:
        # Rated solving: nothing that hints at the solution until it is over.
        return InfoDisplay(
            show_deck_total=False,
            show_rating=True,
            show_move_progress=complete,
            show_theme=complete,
        )
    return InfoDisplay()
