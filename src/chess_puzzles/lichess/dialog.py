from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk

from chess_puzzles.lichess.importer import LichessImportCriteria
from chess_puzzles.lichess.settings import (
    DEFAULT_LICHESS_POPULARITY_MIN,
    DEFAULT_LICHESS_RATING_MAX,
    DEFAULT_LICHESS_RATING_MIN,
    LichessImportSettings,
    load_lichess_settings,
)
from chess_puzzles.lichess.themes import LICHESS_THEMES
from chess_puzzles.settings.theme_repository import UiTheme
from chess_puzzles.ui.theme_selector import ThemeSelector


@dataclass(slots=True, frozen=True)
class LichessImportOptions:
    """User-selected Lichess import parameters."""

    csv_path: Path
    sample_size: int
    rating_min: int = DEFAULT_LICHESS_RATING_MIN
    rating_max: int = DEFAULT_LICHESS_RATING_MAX
    popularity_min: int = DEFAULT_LICHESS_POPULARITY_MIN
    themes: tuple[str, ...] = ()

    def to_criteria(self) -> LichessImportCriteria:
        return LichessImportCriteria(
            sample_size=self.sample_size,
            rating_min=self.rating_min,
            rating_max=self.rating_max,
            popularity_min=self.popularity_min,
            themes=self.themes,
        )

    def to_settings(self) -> LichessImportSettings:
        return LichessImportSettings(
            sample_size=self.sample_size,
            rating_min=self.rating_min,
            rating_max=self.rating_max,
            popularity_min=self.popularity_min,
            themes=self.themes,
        )


class LichessImportDialog(tk.Toplevel):
    """Collect filter options for a one-shot Lichess import.

    ``csv_path`` is the app-wide Lichess CSV (Settings > Paths), resolved by
    the caller; the dialog only displays it."""

    def __init__(
        self,
        parent: tk.Misc,
        theme: UiTheme,
        csv_path: str | Path,
        settings: LichessImportSettings | None = None,
    ) -> None:
        super().__init__(parent, name="lichessimport", class_="ChessPuzzlesLichessImport")
        self.title("Import Lichess CSV")
        self.transient(parent)
        self.resizable(False, False)
        self.result: LichessImportOptions | None = None
        self._settings = settings or load_lichess_settings()
        self._csv_path = Path(csv_path)

        self.sample_size_var = tk.StringVar(value=str(self._settings.sample_size))
        # ttk.Scale writes fractional positions, so these are DoubleVars and
        # every reader rounds.
        self.rating_min_var = tk.DoubleVar(value=self._settings.rating_min)
        self.rating_max_var = tk.DoubleVar(value=self._settings.rating_max)
        self.popularity_min_var = tk.DoubleVar(value=self._settings.popularity_min)
        self.rating_min_display_var = tk.StringVar()
        self.rating_max_display_var = tk.StringVar()
        self.popularity_display_var = tk.StringVar()
        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        self._build_source_row(body)
        self._build_sample_row(body)
        self._build_slider_row(body, "Rating min", self.rating_min_var, self.rating_min_display_var, 2, 0, 3000)
        self._build_slider_row(body, "Rating max", self.rating_max_var, self.rating_max_display_var, 3, 0, 3000)
        self._build_slider_row(body, "Popularity min", self.popularity_min_var, self.popularity_display_var, 4, 0, 100)
        self.theme_selector = ThemeSelector(
            body, theme, LICHESS_THEMES, selected=self._settings.themes, height=7
        )
        self.theme_selector.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(8, 4))

        footer = ttk.Frame(body)
        footer.grid(row=8, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(footer, text="Import & Play", command=self._accept).pack(side=tk.RIGHT, padx=(0, 6))

        body.columnconfigure(1, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Return>", lambda _event: self._accept())
        self.bind("<Escape>", lambda _event: self.destroy())

        self._sync_slider_labels()

    def show_modal(self) -> LichessImportOptions | None:
        self.grab_set()
        self.wait_window()
        return self.result

    def _build_source_row(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Puzzles from").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Label(parent, text=self._csv_path.name, style="Muted.TLabel").grid(
            row=0, column=1, sticky="w", padx=(0, 8), pady=4
        )

    def _build_sample_row(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Number of puzzles").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=self.sample_size_var, width=18).grid(row=1, column=1, sticky="w", pady=4)

    def _build_slider_row(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.DoubleVar,
        display_var: tk.StringVar,
        row: int,
        minimum: int,
        maximum: int,
    ) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=4)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text=label, width=16).grid(row=0, column=0, sticky="w")
        slider = ttk.Scale(
            frame,
            from_=minimum,
            to=maximum,
            orient=tk.HORIZONTAL,
            variable=variable,
            command=lambda value: self._update_slider_label(display_var, value),
            length=340,
        )
        slider.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Label(frame, textvariable=display_var, width=6, anchor=tk.E).grid(row=0, column=2, sticky="e")

    def _sync_slider_labels(self) -> None:
        self.rating_min_display_var.set(str(round(self.rating_min_var.get())))
        self.rating_max_display_var.set(str(round(self.rating_max_var.get())))
        self.popularity_display_var.set(str(round(self.popularity_min_var.get())))

    def _update_slider_label(self, display_var: tk.StringVar, value: str) -> None:
        display_var.set(str(round(float(value))))

    def _accept(self) -> None:
        try:
            sample_size = int(self.sample_size_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid sample size", "Number of puzzles must be a positive integer.", parent=self)
            return
        if sample_size <= 0:
            messagebox.showerror("Invalid sample size", "Number of puzzles must be a positive integer.", parent=self)
            return
        rating_min = round(self.rating_min_var.get())
        rating_max = round(self.rating_max_var.get())
        popularity_min = round(self.popularity_min_var.get())
        if rating_min > rating_max:
            messagebox.showerror("Invalid rating range", "Rating min must be less than or equal to rating max.", parent=self)
            return
        self.result = LichessImportOptions(
            csv_path=self._csv_path,
            sample_size=sample_size,
            rating_min=rating_min,
            rating_max=rating_max,
            popularity_min=popularity_min,
            themes=self.theme_selector.selected,
        )
        self.destroy()
