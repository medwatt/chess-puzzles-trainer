from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chess_puzzles.json_config import load_json_object, save_json_object
from chess_puzzles.platform.paths import user_config_dir


DEFAULT_MINING_SETTINGS_PATH = user_config_dir() / "mining.json"
DEFAULT_MINING_COUNT = 50
DEFAULT_MINING_RATING_MIN = 900
DEFAULT_MINING_RATING_MAX = 1400


@dataclass(frozen=True, slots=True)
class MiningDialogSettings:
    """Persisted defaults for the blunder-generation dialog.

    ``csv_path`` empty means "use the Lichess import's CSV" -- the two
    features share one database file unless the user points them apart.
    """

    csv_path: str = ""
    count: int = DEFAULT_MINING_COUNT
    rating_min: int = DEFAULT_MINING_RATING_MIN
    rating_max: int = DEFAULT_MINING_RATING_MAX


def load_mining_settings(path: str | Path = DEFAULT_MINING_SETTINGS_PATH) -> MiningDialogSettings:
    settings_path = Path(path)
    if not settings_path.exists():
        return MiningDialogSettings()
    data = load_json_object(settings_path, error_message="mining.json must contain a JSON object")
    return MiningDialogSettings(
        csv_path=str(data.get("csv_path", "") or ""),
        count=_int_value(data, "count", DEFAULT_MINING_COUNT, 1, 10_000),
        rating_min=_int_value(data, "rating_min", DEFAULT_MINING_RATING_MIN, 0, 3000),
        rating_max=_int_value(data, "rating_max", DEFAULT_MINING_RATING_MAX, 0, 3000),
    )


def save_mining_settings(
    settings: MiningDialogSettings, path: str | Path = DEFAULT_MINING_SETTINGS_PATH
) -> None:
    save_json_object(
        path,
        {
            "csv_path": settings.csv_path,
            "count": settings.count,
            "rating_min": settings.rating_min,
            "rating_max": settings.rating_max,
        },
    )


def _int_value(data: dict[str, Any], key: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(data.get(key, default))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))
