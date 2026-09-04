from __future__ import annotations

import tkinter as tk

from chess_puzzles.app.app_state import AppState
from chess_puzzles.app.main_window import MainWindow
from chess_puzzles.settings.repository import SettingsRepository
from chess_puzzles.ui.theme import ThemeService


class ChessPuzzlesApplication:
    def __init__(self, settings_repository: SettingsRepository | None = None) -> None:
        self.settings_repository = settings_repository or SettingsRepository()

    def run(self) -> None:
        settings = self.settings_repository.load()
        root = tk.Tk(baseName="chesspuzzles", className="ChessPuzzles")
        theme_service = ThemeService(root, settings.ui_theme_id)
        MainWindow(
            root,
            state=AppState(settings=settings),
            settings_repository=self.settings_repository,
            theme_service=theme_service,
        )
        root.mainloop()


def main() -> None:
    ChessPuzzlesApplication().run()
