"""Persisted board-vision preferences (a self-contained vision.json).

Mirrors ``lichess/settings.py``. Persists the drill selection, the timer, and
each drill's last-used options. Options are stored as their JSON-native
underlying values (an enum's code, a float, a bool), keyed by drill id then
option key -- the options panel maps these back to widget labels on load.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
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
    # drill id -> {option key -> JSON-native underlying value (bool, number, or enum code)}
    drill_options: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)


def load_vision_settings(path: str | Path = DEFAULT_VISION_SETTINGS_PATH) -> VisionSettings:
    settings_path = Path(path)
    if not settings_path.exists():
        return VisionSettings()
    data = load_json_object(settings_path, error_message="vision.json must contain a JSON object")
    return VisionSettings(
        last_drill_id=_string_value(data, "last_drill_id", ""),
        timer_seconds=_timer_value(data.get("timer_seconds", DEFAULT_TIMER_SECONDS)),
        drill_options=_drill_options_value(data.get("drill_options")),
    )


def save_vision_settings(
    settings: VisionSettings,
    path: str | Path = DEFAULT_VISION_SETTINGS_PATH,
) -> None:
    save_json_object(
        path,
        {
            "last_drill_id": settings.last_drill_id,
            "timer_seconds": settings.timer_seconds,
            "drill_options": {drill_id: dict(opts) for drill_id, opts in settings.drill_options.items()},
        },
    )


def _string_value(data: dict[str, Any], key: str, default: str) -> str:
    value = data.get(key, default)
    if not isinstance(value, str):
        return default
    return value.strip()


def _drill_options_value(value: Any) -> dict[str, dict[str, Any]]:
    """Keep only well-formed ``{drill: {key: scalar}}`` entries from JSON.

    Stored values are JSON-native option values (bool, number, or string); anything
    else in a hand-edited or stale file is dropped so an unknown option just falls
    back to the drill's default rather than crashing the loader.
    """
    if not isinstance(value, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for drill_id, options in value.items():
        if not isinstance(drill_id, str) or not isinstance(options, dict):
            continue
        kept = {k: v for k, v in options.items() if isinstance(k, str) and isinstance(v, (bool, int, float, str))}
        if kept:
            result[drill_id] = kept
    return result


def _timer_value(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in TIMER_CHOICES:
        return DEFAULT_TIMER_SECONDS
    return value
