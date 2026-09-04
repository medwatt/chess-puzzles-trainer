from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chess_puzzles.json_config import int_value, load_json_object, save_json_object
from chess_puzzles.lichess.filters import NUMERIC_FILTERS
from chess_puzzles.lichess.importer import THEME_MODE_ALL, THEME_MODE_ANY
from chess_puzzles.lichess.vocabulary import LICHESS_OPENINGS, LICHESS_THEMES
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
    # One field per NUMERIC_FILTERS row; the loader and writer below are
    # driven by that table, so a new filter needs no changes here beyond the
    # field itself.
    rating_min: int = DEFAULT_LICHESS_RATING_MIN
    rating_max: int = DEFAULT_LICHESS_RATING_MAX
    moves_min: int = 1
    moves_max: int = 13
    popularity_min: int = DEFAULT_LICHESS_POPULARITY_MIN
    rating_deviation_max: int = 500
    nb_plays_min: int = 0
    themes: tuple[str, ...] = ()
    theme_mode: str = THEME_MODE_ANY
    themes_excluded: tuple[str, ...] = ()
    openings: tuple[str, ...] = ()


def load_lichess_settings(path: str | Path = DEFAULT_LICHESS_SETTINGS_PATH) -> LichessImportSettings:
    settings_path = Path(path)
    if not settings_path.exists():
        return LichessImportSettings()
    data = load_json_object(settings_path, error_message="lichess.json must contain a JSON object")
    numeric = {
        item.field: int_value(data, item.field, item.default, item.minimum, item.maximum)
        for item in NUMERIC_FILTERS
    }
    mode = data.get("theme_mode")
    return LichessImportSettings(
        sample_size=int_value(data, "sample_size", DEFAULT_LICHESS_SAMPLE_SIZE, 1, 10_000),
        themes=_string_tuple(data.get("themes", ()), LICHESS_THEMES),
        theme_mode=mode if mode in (THEME_MODE_ANY, THEME_MODE_ALL) else THEME_MODE_ANY,
        themes_excluded=_string_tuple(data.get("themes_excluded", ()), LICHESS_THEMES),
        openings=_string_tuple(data.get("openings", ()), LICHESS_OPENINGS),
        **numeric,
    )


def save_lichess_settings(
    settings: LichessImportSettings,
    path: str | Path = DEFAULT_LICHESS_SETTINGS_PATH,
) -> None:
    save_json_object(
        path,
        {
            "sample_size": settings.sample_size,
            **{item.field: getattr(settings, item.field) for item in NUMERIC_FILTERS},
            "themes": list(settings.themes),
            "theme_mode": settings.theme_mode,
            "themes_excluded": list(settings.themes_excluded),
            "openings": list(settings.openings),
        },
    )


def _string_tuple(values: Any, vocabulary: tuple[str, ...]) -> tuple[str, ...]:
    """Keep only known values, in order, without duplicates.

    A tag Lichess has retired since the file was written is dropped rather
    than carried forward as a filter that can never match."""
    if not isinstance(values, list):
        return ()
    allowed = set(vocabulary)
    unique: list[str] = []
    for value in values:
        if isinstance(value, str):
            item = value.strip()
            if item and item in allowed and item not in unique:
                unique.append(item)
    return tuple(unique)
