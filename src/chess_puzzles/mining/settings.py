from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chess_puzzles.json_config import int_value, load_json_object, save_json_object
from chess_puzzles.platform.paths import user_config_dir


DEFAULT_MINING_SETTINGS_PATH = user_config_dir() / "mining.json"
DEFAULT_MINING_COUNT = 50
DEFAULT_MINING_RATING_MIN = 900
DEFAULT_MINING_RATING_MAX = 1400


@dataclass(frozen=True, slots=True)
class MiningDialogSettings:
    """Persisted defaults for the blunder-generation dialog.

    The CSV path is not here: every CSV-consuming feature reads the shared
    ``lichess_csv_path`` from AppSettings (Settings > Paths).
    """

    count: int = DEFAULT_MINING_COUNT
    rating_min: int = DEFAULT_MINING_RATING_MIN
    rating_max: int = DEFAULT_MINING_RATING_MAX


def load_mining_settings(path: str | Path = DEFAULT_MINING_SETTINGS_PATH) -> MiningDialogSettings:
    settings_path = Path(path)
    if not settings_path.exists():
        return MiningDialogSettings()
    data = load_json_object(settings_path, error_message="mining.json must contain a JSON object")
    return MiningDialogSettings(
        count=int_value(data, "count", DEFAULT_MINING_COUNT, 1, 10_000),
        rating_min=int_value(data, "rating_min", DEFAULT_MINING_RATING_MIN, 0, 3000),
        rating_max=int_value(data, "rating_max", DEFAULT_MINING_RATING_MAX, 0, 3000),
    )


def save_mining_settings(
    settings: MiningDialogSettings, path: str | Path = DEFAULT_MINING_SETTINGS_PATH
) -> None:
    save_json_object(
        path,
        {
            "count": settings.count,
            "rating_min": settings.rating_min,
            "rating_max": settings.rating_max,
        },
    )
