"""Drawing math shared by the live canvas and the SVG exporter.

Square parity, coordinate-label placement, and arrow shapes need to
match in both renderers. Each backend translates these results into
its own drawing calls.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import chess

from chess_puzzles.board.board_state import BoardRenderState
from chess_puzzles.board.board_theme import AnnotationTheme
from chess_puzzles.board.geometry import BoardGeometry


def is_light_square(square: int) -> bool:
    return (chess.square_file(square) + chess.square_rank(square)) % 2 != 0


def square_fill(state: BoardRenderState, square: int) -> str:
    theme = state.board_theme
    return theme.light_square if is_light_square(square) else theme.dark_square


def coordinate_color(state: BoardRenderState, square: int) -> str:
    light = state.board_theme.coordinate_light or state.board_theme.dark_square
    dark = state.board_theme.coordinate_dark or state.board_theme.light_square
    return light if is_light_square(square) else dark


def coordinate_font_size(geometry: BoardGeometry) -> int:
    # Pixel size for both backends.
    return max(9, round(geometry.square_size * 0.18))


def coordinate_cap_height(geometry: BoardGeometry) -> int:
    # Approximate digit cap height (~0.76 of the font size). Both backends place
    # rank labels by their baseline this far below the top edge, so they end up
    # in the same spot regardless of renderer.
    return round(coordinate_font_size(geometry) * 0.76)


@dataclass(frozen=True, slots=True)
class CoordinateLabel:
    x: float
    y: float
    text: str
    color: str
    anchor: str  # Tk-style anchor: "se" for file labels, "nw" for rank labels


def coordinate_labels(state: BoardRenderState, geometry: BoardGeometry) -> list[CoordinateLabel]:
    labels: list[CoordinateLabel] = []
    pad = geometry.square_size * 0.075
    for display_file in range(8):
        square = geometry.square_from_display(display_file, 7, state.flipped)
        labels.append(
            CoordinateLabel(
                x=geometry.left + (display_file + 1) * geometry.square_size - pad,
                y=geometry.top + 8 * geometry.square_size - pad,
                text=chess.FILE_NAMES[chess.square_file(square)],
                color=coordinate_color(state, square),
                anchor="se",
            )
        )
    for display_rank in range(8):
        square = geometry.square_from_display(0, display_rank, state.flipped)
        labels.append(
            CoordinateLabel(
                x=geometry.left + pad,
                y=geometry.top + display_rank * geometry.square_size + pad,
                text=chess.RANK_NAMES[chess.square_rank(square)],
                color=coordinate_color(state, square),
                anchor="nw",
            )
        )
    return labels


@dataclass(frozen=True, slots=True)
class ArrowShape:
    shaft_start: tuple[float, float]
    shaft_end: tuple[float, float]
    width: float
    # Head triangle as (tip_x, tip_y, left_x, left_y, right_x, right_y).
    head: tuple[float, float, float, float, float, float]


def arrow_shape(
    geometry: BoardGeometry,
    theme: AnnotationTheme,
    origin: int,
    target: int,
    flipped: bool,
    width_scale: float,
) -> ArrowShape | None:
    if origin == target:
        return None
    sx, sy = geometry.square_center(origin, flipped)
    ex, ey = geometry.square_center(target, flipped)
    dx = ex - sx
    dy = ey - sy
    length = math.hypot(dx, dy)
    if length < 1:
        return None
    ux = dx / length
    uy = dy / length
    square_size = geometry.square_size
    head_length = square_size * theme.arrow_head_length_scale
    head_width = square_size * theme.arrow_head_width_scale
    perp_x = -uy
    perp_y = ux
    base_x = ex - ux * head_length
    base_y = ey - uy * head_length
    return ArrowShape(
        shaft_start=(
            sx + ux * square_size * theme.arrow_start_inset_scale,
            sy + uy * square_size * theme.arrow_start_inset_scale,
        ),
        shaft_end=(
            ex - ux * square_size * theme.arrow_target_inset_scale,
            ey - uy * square_size * theme.arrow_target_inset_scale,
        ),
        width=max(4.0, square_size * width_scale),
        head=(
            ex,
            ey,
            base_x + perp_x * head_width,
            base_y + perp_y * head_width,
            base_x - perp_x * head_width,
            base_y - perp_y * head_width,
        ),
    )
