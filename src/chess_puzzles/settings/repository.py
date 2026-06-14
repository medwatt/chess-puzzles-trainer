from __future__ import annotations

import json
from pathlib import Path

from chess_puzzles.json_config import save_json_object
from chess_puzzles.platform.paths import user_config_dir
from chess_puzzles.settings.model import AppSettings


class SettingsRepository:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or user_config_dir() / "settings.json"

    def load(self) -> AppSettings:
        if not self.path.exists():
            return AppSettings()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AppSettings()
        if not isinstance(data, dict):
            return AppSettings()
        return AppSettings.from_json(data)

    def save(self, settings: AppSettings) -> None:
        save_json_object(self.path, settings.to_json())
