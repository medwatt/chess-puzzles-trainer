from __future__ import annotations

from chess_puzzles.board import BoardPresentation, BoardPresenter, PresentationPolicy
from chess_puzzles.board.board_theme import default_board_theme, default_piece_theme


class _BoardSpy:
    def __init__(self) -> None:
        self.theme_calls = 0
        self.coordinates: list[bool] = []

    def set_theme(self, *_args, **_kwargs) -> None:
        self.theme_calls += 1

    def set_surround_background(self, _color: str) -> None:
        pass

    def set_coordinates_visible(self, enabled: bool) -> None:
        self.coordinates.append(enabled)


def _presentation(*, show_coordinates: bool = False) -> BoardPresentation:
    return BoardPresentation(
        board_theme=default_board_theme(),
        piece_theme=default_piece_theme(),
        show_coordinates=show_coordinates,
    )


def test_presenter_policy_can_leave_coordinates_to_the_board() -> None:
    presenter = BoardPresenter(_presentation(show_coordinates=True))
    board = _BoardSpy()

    presenter.register(board, PresentationPolicy(coordinates=False))
    presenter.update(show_coordinates=False)

    assert board.theme_calls == 2
    assert board.coordinates == []


def test_presenter_applies_coordinates_by_default() -> None:
    presenter = BoardPresenter(_presentation(show_coordinates=True))
    board = _BoardSpy()

    presenter.register(board)
    presenter.update(show_coordinates=False)

    assert board.coordinates == [True, False]
