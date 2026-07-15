from __future__ import annotations

from chess_puzzles.app.info_display import InfoDisplay, info_display_for
from chess_puzzles.store import DECK_KIND_ARENA, DECK_KIND_REPERTOIRE, DECK_KIND_TACTICS


def test_ordinary_decks_show_everything() -> None:
    for kind in (DECK_KIND_TACTICS, DECK_KIND_REPERTOIRE, ""):
        for complete in (False, True):
            assert info_display_for(kind, complete=complete) == InfoDisplay()


def test_arena_hides_solution_hints_until_solved() -> None:
    solving = info_display_for(DECK_KIND_ARENA, complete=False)
    assert not solving.show_deck_total
    assert solving.show_rating
    assert not solving.show_move_progress
    assert not solving.show_theme

    solved = info_display_for(DECK_KIND_ARENA, complete=True)
    assert solved.show_move_progress
    assert solved.show_theme
