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
    # Preferences below are the ones described in settings.options; every
    # one of them has a row there and is edited through the Options dialog.
    show_coordinates: bool = False
    sound_enabled: bool = False
    show_evaluation_bar: bool = True
    show_session_stats: bool = True
    show_user_notes: bool = True
    reflow_comments: bool = False
    auto_advance: bool = True
    stop_at_comments: bool = True
    show_avoided_mistakes: bool = True
    step_through_lines: bool = False
    start_lines_at_divergence: bool = True
    demonstrate_new_lines: bool = True
    font_family: str = ""
    font_size: int = 10
    font_style: str = "regular"
    recent_database_paths: tuple[str, ...] = field(default_factory=tuple)
    default_database_directory: str | None = None
    piece_assets_directory: str | None = None
    # The one Lichess puzzle CSV every feature samples from (import, rated
    # sessions, board vision, blunder mining). Configured in Settings > Paths.
    lichess_csv_path: str | None = None

    def to_json(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "AppSettings":
        defaults = cls()

        def flag(key: str, default: bool) -> bool:
            return bool(data.get(key, default))

        recent = data.get("recent_database_paths", ())
        return cls(
            ui_theme_id=str(data.get("ui_theme_id", defaults.ui_theme_id)),
            board_theme_id=str(data.get("board_theme_id", defaults.board_theme_id)),
            piece_theme_id=str(data.get("piece_theme_id", defaults.piece_theme_id)),
            show_coordinates=flag("show_coordinates", defaults.show_coordinates),
            sound_enabled=flag("sound_enabled", defaults.sound_enabled),
            show_evaluation_bar=flag("show_evaluation_bar", defaults.show_evaluation_bar),
            show_session_stats=flag("show_session_stats", defaults.show_session_stats),
            show_user_notes=flag("show_user_notes", defaults.show_user_notes),
            # Renamed from "clean_comments": the setting reflows whitespace,
            # it never removes anything the author wrote.
            reflow_comments=flag(
                "reflow_comments", flag("clean_comments", defaults.reflow_comments)
            ),
            # Renamed from "auto_next_enabled".
            auto_advance=flag("auto_advance", flag("auto_next_enabled", defaults.auto_advance)),
            # Renamed from "pause_for_comment", which covered the same two
            # places: solving, and a line the app plays out.
            stop_at_comments=flag(
                "stop_at_comments", flag("pause_for_comment", defaults.stop_at_comments)
            ),
            show_avoided_mistakes=flag("show_avoided_mistakes", defaults.show_avoided_mistakes),
            step_through_lines=_step_through_lines(data, defaults.step_through_lines),
            start_lines_at_divergence=flag(
                "start_lines_at_divergence", defaults.start_lines_at_divergence
            ),
            demonstrate_new_lines=flag("demonstrate_new_lines", defaults.demonstrate_new_lines),
            font_family=str(data.get("font_family", defaults.font_family)),
            font_size=int(data.get("font_size", defaults.font_size)),
            font_style=str(data.get("font_style", defaults.font_style)),
            recent_database_paths=tuple(str(path) for path in recent),
            default_database_directory=_optional_path(data.get("default_database_directory")),
            piece_assets_directory=_optional_path(data.get("piece_assets_directory")),
            lichess_csv_path=_optional_path(data.get("lichess_csv_path")),
        )


def _step_through_lines(data: dict[str, Any], default: bool) -> bool:
    """Renamed from ``pause_playback_each_move``, via a short-lived
    ``playback_pace`` whose "pause at comments" value is now what
    ``stop_at_comments`` says."""
    if "step_through_lines" in data:
        return bool(data["step_through_lines"])
    if "playback_pace" in data:
        return data["playback_pace"] == "every_move"
    return bool(data.get("pause_playback_each_move", default))


def _optional_path(value: Any) -> str | None:
    if value is None or not str(value).strip():
        return None
    return str(Path(str(value)).expanduser())
