from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from chess_puzzles.board.board_theme import (
    AnnotationTheme,
    BoardTheme,
    PieceTheme,
    default_annotation_theme,
)

if TYPE_CHECKING:
    from chess_puzzles.board.board_view import BoardView


@dataclass(frozen=True, slots=True)
class PresentationPolicy:
    """Which global presentation settings a board follows."""

    theme: bool = True
    surround_background: bool = True
    coordinates: bool = True


@dataclass(frozen=True, slots=True)
class BoardPresentation:
    """Board, piece, and annotation theme for every board in the app."""

    board_theme: BoardTheme
    piece_theme: PieceTheme
    annotation_theme: AnnotationTheme = field(default_factory=default_annotation_theme)
    surround_background: str | None = None
    show_coordinates: bool = False

    def with_changes(self, **changes: object) -> "BoardPresentation":
        return replace(self, **changes)

    def apply(self, board: "BoardView", policy: PresentationPolicy | None = None) -> None:
        policy = policy or PresentationPolicy()
        if policy.theme:
            board.set_theme(
                self.board_theme,
                piece_theme=self.piece_theme,
                annotation_theme=self.annotation_theme,
            )
        if policy.surround_background and self.surround_background is not None:
            board.set_surround_background(self.surround_background)
        if policy.coordinates:
            board.set_coordinates_visible(self.show_coordinates)


class BoardPresenter:
    """When the theme changes, pushes the new settings to every board."""

    def __init__(self, presentation: BoardPresentation) -> None:
        self._presentation = presentation
        self._boards: list[tuple["BoardView", PresentationPolicy]] = []

    @property
    def presentation(self) -> BoardPresentation:
        return self._presentation

    def update(self, **changes: object) -> BoardPresentation:
        self._presentation = self._presentation.with_changes(**changes)
        for board, policy in self._boards:
            self._presentation.apply(board, policy)
        return self._presentation

    def register(self, board: "BoardView", policy: PresentationPolicy | None = None) -> None:
        policy = policy or PresentationPolicy()
        for index, (existing, _policy) in enumerate(self._boards):
            if existing is board:
                self._boards[index] = (board, policy)
                break
        else:
            self._boards.append((board, policy))
        self._presentation.apply(board, policy)

    def unregister(self, board: "BoardView") -> None:
        self._boards = [(existing, policy) for existing, policy in self._boards if existing is not board]
