from __future__ import annotations

from dataclasses import dataclass

from chess_puzzles.settings.model import AppSettings


@dataclass(slots=True)
class AppState:
    settings: AppSettings
