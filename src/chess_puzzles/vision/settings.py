"""Persisted board-vision preferences (a self-contained vision.json).

Mirrors ``lichess/settings.py``. Only the drill selection and timer persist
here; per-drill knobs (scope, pawns, negatives) deliberately default in the
drill classes and reset each session, keeping this a small fixed schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chess_puzzles.json_config import load_json_object, save_json_object
from chess_puzzles.platform.paths import user_config_dir

DEFAULT_VISION_SETTINGS_PATH = user_config_dir() / "vision.json"
DEFAULT_TIMER_SECONDS = 5
TIMER_CHOICES: tuple[int, ...] = (0, 3, 5, 10)  # 0 == untimed


@dataclass(frozen=True, slots=True)
class VisionSettings:
    last_drill_id: str = ""
    timer_seconds: int = DEFAULT_TIMER_SECONDS


def load_vision_settings(path: str | Path = DEFAULT_VISION_SETTINGS_PATH) -> VisionSettings:
    settings_path = Path(path)
    if not settings_path.exists():
        return VisionSettings()
    data = load_json_object(settings_path, error_message="vision.json must contain a JSON object")
    return VisionSettings(
        last_drill_id=_string_value(data, "last_drill_id", ""),
        timer_seconds=_timer_value(data.get("timer_seconds", DEFAULT_TIMER_SECONDS)),
    )


def save_vision_settings(
    settings: VisionSettings,
    path: str | Path = DEFAULT_VISION_SETTINGS_PATH,
) -> None:
    save_json_object(
        path,
        {"last_drill_id": settings.last_drill_id, "timer_seconds": settings.timer_seconds},
    )


def _string_value(data: dict[str, Any], key: str, default: str) -> str:
    value = data.get(key, default)
    if not isinstance(value, str):
        return default
    return value.strip()


def _timer_value(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in TIMER_CHOICES:
        return DEFAULT_TIMER_SECONDS
    return value
