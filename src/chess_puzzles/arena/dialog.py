from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from chess_puzzles.arena.service import ArenaConfig, DEFAULT_BATCH_SIZE
from chess_puzzles.lichess.settings import load_lichess_settings
from chess_puzzles.lichess.vocabulary import LICHESS_THEMES
from chess_puzzles.settings.theme_repository import UiTheme
from chess_puzzles.ui.theme_selector import ThemeSelector
from chess_puzzles.ui.modal import ModalParent, run_modal


class ArenaStartDialog(tk.Toplevel):
    """Collect the inputs for a new rated session.

    ``csv_path`` is the app-wide Lichess CSV (Settings > Paths), resolved by
    the caller; the dialog only displays it. The starting rating pre-fills
    from the most recent session's current rating (passed in by the caller).
    Themes are optional -- empty means any theme.
    """

    def __init__(
        self,
        parent: ModalParent,
        theme: UiTheme,
        csv_path: str | Path,
        *,
        default_rating: int = 1500,
    ) -> None:
        super().__init__(parent, name="arenastart", class_="ChessPuzzlesArenaStart")
        self.title("Start Rated Session")
        self.transient(parent)
        self.resizable(False, False)
        self.result: ArenaConfig | None = None
        self._csv_path = Path(csv_path)
        settings = load_lichess_settings()

        self.rating_var = tk.StringVar(value=str(default_rating))
        self.popularity_var = tk.StringVar(value=str(settings.popularity_min))
        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(body, text="Puzzles from").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Label(body, text=self._csv_path.name, style="Muted.TLabel").grid(
            row=0, column=1, sticky="w", padx=(0, 8), pady=4
        )

        ttk.Label(body, text="Starting rating").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=self.rating_var, width=10).grid(
            row=1, column=1, sticky="w", pady=4
        )

        ttk.Label(body, text="Popularity min").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=self.popularity_var, width=10).grid(
            row=2, column=1, sticky="w", pady=4
        )

        self.theme_selector = ThemeSelector(
            body, theme, LICHESS_THEMES, title="Themes (optional)", height=4
        )
        self.theme_selector.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 4))

        footer = ttk.Frame(body)
        footer.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(footer, text="Start", command=self._accept).pack(side=tk.RIGHT, padx=(0, 6))

        body.columnconfigure(1, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Return>", lambda _event: self._accept())
        self.bind("<Escape>", lambda _event: self.destroy())

    def show_modal(self) -> ArenaConfig | None:
        run_modal(self)
        return self.result

    def _accept(self) -> None:
        try:
            rating = int(self.rating_var.get().strip())
        except ValueError:
            rating = -1
        if not 0 <= rating <= 3000:
            messagebox.showerror(
                "Invalid rating", "Starting rating must be between 0 and 3000.", parent=self
            )
            return
        try:
            popularity = int(self.popularity_var.get().strip() or "0")
        except ValueError:
            popularity = -1
        if not 0 <= popularity <= 100:
            messagebox.showerror(
                "Invalid popularity", "Popularity must be between 0 and 100.", parent=self
            )
            return
        self.result = ArenaConfig(
            csv_path=str(self._csv_path),
            start_rating=rating,
            popularity_min=popularity,
            themes=self.theme_selector.selected,
            batch_size=DEFAULT_BATCH_SIZE,
        )
        self.destroy()
