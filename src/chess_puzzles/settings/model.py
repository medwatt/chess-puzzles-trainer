from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from chess_puzzles.constants import (
    DEFAULT_BOARD_THEME_ID,
    DEFAULT_PIECE_THEME_ID,
    DEFAULT_UI_THEME_ID,
)


@dataclass(frozen=True, slots=True)
class AppSettings:
    ui_theme_id: str = DEFAULT_UI_THEME_ID
    board_theme_id: str = DEFAULT_BOARD_THEME_ID
    piece_theme_id: str = DEFAULT_PIECE_THEME_ID
    show_coordinates: bool = False
    sound_enabled: bool = False
    show_pgn_after_solve: bool = False
    show_evaluation_bar: bool = True
    show_session_stats: bool = True
    show_user_notes: bool = True
    auto_next_enabled: bool = True
    clean_comments: bool = False
    pause_for_comment: bool = True
    pause_playback_each_move: bool = False
    start_lines_at_divergence: bool = True
    demonstrate_new_lines: bool = True
    font_family: str = ""
    font_size: int = 10
    font_style: str = "regular"
    recent_database_paths: tuple[str, ...] = field(default_factory=tuple)
    default_database_directory: str | None = None
    piece_assets_directory: str | None = None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "AppSettings":
        defaults = cls()
        recent = data.get("recent_database_paths", ())
        default_dir = _optional_path(data.get("default_database_directory"))
        pieces_dir = _optional_path(data.get("piece_assets_directory"))
        return cls(
            ui_theme_id=str(data.get("ui_theme_id", defaults.ui_theme_id)),
            board_theme_id=str(data.get("board_theme_id", defaults.board_theme_id)),
            piece_theme_id=str(data.get("piece_theme_id", defaults.piece_theme_id)),
            show_coordinates=bool(data.get("show_coordinates", defaults.show_coordinates)),
            sound_enabled=bool(data.get("sound_enabled", defaults.sound_enabled)),
            show_pgn_after_solve=bool(
                data.get("show_pgn_after_solve", defaults.show_pgn_after_solve)
            ),
            show_evaluation_bar=bool(data.get("show_evaluation_bar", defaults.show_evaluation_bar)),
            show_session_stats=bool(data.get("show_session_stats", defaults.show_session_stats)),
            show_user_notes=bool(data.get("show_user_notes", defaults.show_user_notes)),
            auto_next_enabled=bool(data.get("auto_next_enabled", defaults.auto_next_enabled)),
            clean_comments=bool(data.get("clean_comments", defaults.clean_comments)),
            pause_for_comment=bool(data.get("pause_for_comment", defaults.pause_for_comment)),
            pause_playback_each_move=bool(
                data.get("pause_playback_each_move", defaults.pause_playback_each_move)
            ),
            start_lines_at_divergence=bool(
                data.get("start_lines_at_divergence", defaults.start_lines_at_divergence)
            ),
            demonstrate_new_lines=bool(
                data.get("demonstrate_new_lines", defaults.demonstrate_new_lines)
            ),
            font_family=str(data.get("font_family", defaults.font_family)),
            font_size=int(data.get("font_size", defaults.font_size)),
            font_style=str(data.get("font_style", defaults.font_style)),
            recent_database_paths=tuple(str(path) for path in recent),
            default_database_directory=default_dir,
            piece_assets_directory=pieces_dir,
        )


def _optional_path(value: Any) -> str | None:
    if value is None or not str(value).strip():
        return None
    return str(Path(str(value)).expanduser())
