"""Reusable board system for chess workflows."""

from chess_puzzles.board.annotations import (
    AnnotationColor,
    ArrowAnnotation,
    BoardAnnotations,
    CircleAnnotation,
    SquareAnnotation,
)
from chess_puzzles.board.board_state import BoardCapabilities, BoardRenderState
from chess_puzzles.board.board_theme import (
    AnnotationTheme,
    BoardTheme,
    PieceTheme,
    default_annotation_theme,
    default_board_theme,
    default_piece_theme,
)
from chess_puzzles.board.board_view import BoardView
from chess_puzzles.board.presentation import BoardPresentation, BoardPresenter, PresentationPolicy
from chess_puzzles.board.shortcuts import BoardShortcuts
from chess_puzzles.board.svg_backend import snapshot_to_svg, state_to_svg

__all__ = [
    "AnnotationColor",
    "AnnotationTheme",
    "ArrowAnnotation",
    "BoardAnnotations",
    "BoardCapabilities",
    "BoardPresentation",
    "BoardPresenter",
    "BoardRenderState",
    "BoardShortcuts",
    "BoardTheme",
    "BoardView",
    "CircleAnnotation",
    "PieceTheme",
    "PresentationPolicy",
    "SquareAnnotation",
    "default_annotation_theme",
    "default_board_theme",
    "default_piece_theme",
    "snapshot_to_svg",
    "state_to_svg",
]
