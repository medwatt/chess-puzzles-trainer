from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chess_puzzles.json_config import int_value, load_json_object, save_json_object
from chess_puzzles.lichess.themes import LICHESS_THEMES
from chess_puzzles.platform.paths import user_config_dir


DEFAULT_LICHESS_SETTINGS_PATH = user_config_dir() / "lichess.json"
DEFAULT_LICHESS_SAMPLE_SIZE = 10
DEFAULT_LICHESS_RATING_MIN = 800
DEFAULT_LICHESS_RATING_MAX = 1200
DEFAULT_LICHESS_POPULARITY_MIN = 80


@dataclass(frozen=True, slots=True)
class LichessImportSettings:
    """Persisted filter defaults for the Lichess import dialog.

    The CSV path itself is NOT here: it lives in AppSettings
    (``lichess_csv_path``, Settings > Paths) because several features share
    it (import, rated sessions, board vision, blunder mining)."""

    sample_size: int = DEFAULT_LICHESS_SAMPLE_SIZE
    rating_min: int = DEFAULT_LICHESS_RATING_MIN
    rating_max: int = DEFAULT_LICHESS_RATING_MAX
    popularity_min: int = DEFAULT_LICHESS_POPULARITY_MIN
    themes: tuple[str, ...] = ()


def load_lichess_settings(path: str | Path = DEFAULT_LICHESS_SETTINGS_PATH) -> LichessImportSettings:
    settings_path = Path(path)
    if not settings_path.exists():
        return LichessImportSettings()
    data = load_json_object(settings_path, error_message="lichess.json must contain a JSON object")
    return LichessImportSettings(
        sample_size=int_value(data, "sample_size", DEFAULT_LICHESS_SAMPLE_SIZE, 1, 10_000),
        rating_min=int_value(data, "rating_min", DEFAULT_LICHESS_RATING_MIN, 0, 3000),
        rating_max=int_value(data, "rating_max", DEFAULT_LICHESS_RATING_MAX, 0, 3000),
        popularity_min=int_value(data, "popularity_min", DEFAULT_LICHESS_POPULARITY_MIN, 0, 100),
        themes=_string_tuple(data.get("themes", ())),
    )


def save_lichess_settings(
    settings: LichessImportSettings,
    path: str | Path = DEFAULT_LICHESS_SETTINGS_PATH,
) -> None:
    save_json_object(
        path,
        {
            "sample_size": settings.sample_size,
            "rating_min": settings.rating_min,
            "rating_max": settings.rating_max,
            "popularity_min": settings.popularity_min,
            "themes": list(settings.themes),
        },
    )


def _string_tuple(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    unique: list[str] = []
    for value in values:
        if isinstance(value, str):
            item = value.strip()
            if item and item in LICHESS_THEMES and item not in unique:
                unique.append(item)
    return tuple(unique)
