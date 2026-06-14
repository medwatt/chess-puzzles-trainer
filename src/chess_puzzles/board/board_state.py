from __future__ import annotations

from dataclasses import dataclass, field, replace

import chess

from chess_puzzles.board.annotations import AnnotationColor, BoardAnnotations
from chess_puzzles.board.control import ControlOverlayMode
from chess_puzzles.constants import FLASH_DEFAULT_COLOR
from chess_puzzles.board.board_theme import (
    AnnotationTheme,
    BoardTheme,
    PieceTheme,
    default_annotation_theme,
    default_board_theme,
    default_piece_theme,
)


@dataclass(frozen=True, slots=True)
class BoardCapabilities:
    movable_pieces: bool = True
    annotations: bool = True
    last_move: bool = True
    legal_move_hints: bool = True
    # When set, a left click on any square (empty included) is reported as a
    # SquareSelected answer and no move/drag is attempted -- used by board vision
    # drills, where clicks are answers rather than moves.
    select_any_square: bool = False


@dataclass(frozen=True, slots=True)
class FlashState:
    squares: tuple[int, ...] = ()
    color: str = FLASH_DEFAULT_COLOR


@dataclass(frozen=True, slots=True)
class MoveAnimationState:
    move: chess.Move
    piece: chess.Piece
    progress: float = 0.0


@dataclass(frozen=True, slots=True)
class DragPieceState:
    origin: int
    piece: chess.Piece
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class BoardRenderState:
    board: chess.Board = field(default_factory=chess.Board)
    flipped: bool = False
    board_theme: BoardTheme = field(default_factory=default_board_theme)
    piece_theme: PieceTheme = field(default_factory=default_piece_theme)
    annotation_theme: AnnotationTheme = field(default_factory=default_annotation_theme)
    capabilities: BoardCapabilities = field(default_factory=BoardCapabilities)
    show_coordinates: bool = False
    selected_square: int | None = None
    legal_targets: frozenset[int] = field(default_factory=frozenset)
    annotations: BoardAnnotations = field(default_factory=BoardAnnotations.empty)
    last_move: chess.Move | None = None
    flash: FlashState | None = None
    animation: MoveAnimationState | None = None
    drag_piece: DragPieceState | None = None
    live_arrow: tuple[int, int] | None = None
    live_arrow_color: AnnotationColor = AnnotationColor.GREEN
    threat_move: chess.Move | None = None
    control_overlay: ControlOverlayMode = ControlOverlayMode.OFF

    def copy_with(self, **changes: object) -> "BoardRenderState":
        if "board" in changes:
            board = changes["board"]
            if isinstance(board, chess.Board):
                changes["board"] = board.copy(stack=False)
        return replace(self, **changes)


@dataclass(frozen=True, slots=True)
class BoardSnapshot:
    state: BoardRenderState
    width: int
    height: int
