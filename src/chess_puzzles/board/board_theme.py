from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from chess_puzzles.board.annotations import AnnotationColor
from chess_puzzles.constants import DEFAULT_PIECE_THEME_ID
from chess_puzzles.platform.paths import assets_dir


@dataclass(frozen=True, slots=True)
class BoardTheme:
    id: str
    name: str
    light_square: str
    dark_square: str
    selected_square: str
    legal_target: str
    coordinate_light: str | None
    coordinate_dark: str | None
    texture_light: Path | None = None
    texture_dark: Path | None = None


@dataclass(frozen=True, slots=True)
class PieceTheme:
    id: str
    name: str
    image_directory: Path | None = None
    svg_directory: Path | None = None
    scale: float = 0.82


@dataclass(frozen=True, slots=True)
class AnnotationTheme:
    colors: dict[AnnotationColor, str] = field(
        default_factory=lambda: {
            AnnotationColor.GREEN: "#2f8f46",
            AnnotationColor.RED: "#cc3333",
            AnnotationColor.BLUE: "#2f64c8",
            AnnotationColor.YELLOW: "#d4a017",
        }
    )
    arrow_stroke_scale: float = 0.075
    arrow_head_width_scale: float = 0.16
    arrow_head_length_scale: float = 0.33
    arrow_start_inset_scale: float = 0.18
    arrow_target_inset_scale: float = 0.30
    circle_radius_scale: float = 0.47
    square_stroke_scale: float = 0.07
    last_move_color: str = "#6f6f6f"
    last_move_stroke_scale: float = 0.07
    flash_opacity: float = 0.58
    threat_color: str = "#cc2f2f"
    danger_color: str = "#d96545"
    control_white_color: str = "#3f8efc"
    control_black_color: str = "#e4574d"


def default_board_theme() -> BoardTheme:
    return BoardTheme(
        id="classic",
        name="Classic",
        light_square="#f0d9b5",
        dark_square="#b58863",
        selected_square="#f6f669",
        legal_target="#7fb069",
        coordinate_light="#b58863",
        coordinate_dark="#f0d9b5",
    )


def default_piece_theme() -> PieceTheme:
    return PieceTheme(
        id=DEFAULT_PIECE_THEME_ID,
        name=DEFAULT_PIECE_THEME_ID,
        image_directory=assets_dir() / "img" / "pieces" / DEFAULT_PIECE_THEME_ID,
    )


def default_annotation_theme() -> AnnotationTheme:
    return AnnotationTheme()
