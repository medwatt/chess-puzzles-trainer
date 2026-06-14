from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

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
            csv_path=str(self.csv_path),
            sample_size=self.sample_size,
            rating_min=self.rating_min,
            rating_max=self.rating_max,
            popularity_min=self.popularity_min,
            themes=self.themes,
        )


class LichessImportDialog(tk.Toplevel):
    """Collect CSV location and filter options for a one-shot Lichess import."""

    def __init__(self, parent: tk.Misc, theme: UiTheme, settings: LichessImportSettings | None = None) -> None:
        super().__init__(parent, name="lichessimport", class_="ChessPuzzlesLichessImport")
        self.title("Import Lichess CSV")
        self.transient(parent)
        self.resizable(False, False)
        self.result: LichessImportOptions | None = None
        self._theme = theme
        self._settings = settings or load_lichess_settings()

        self.csv_path_var = tk.StringVar(value=self._settings.csv_path)
        self.sample_size_var = tk.StringVar(value=str(self._settings.sample_size))
        # ttk.Scale writes fractional positions, so these are DoubleVars and
        # every reader rounds.
        self.rating_min_var = tk.DoubleVar(value=self._settings.rating_min)
        self.rating_max_var = tk.DoubleVar(value=self._settings.rating_max)
        self.popularity_min_var = tk.DoubleVar(value=self._settings.popularity_min)
        self.theme_choice_var = tk.StringVar(value=self._theme_choice_default())
        self.rating_min_display_var = tk.StringVar()
        self.rating_max_display_var = tk.StringVar()
        self.popularity_display_var = tk.StringVar()
        self._selected_themes: list[str] = list(self._settings.themes)

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        self._build_source_row(body)
        self._build_sample_row(body)
        self._build_slider_row(body, "Rating min", self.rating_min_var, self.rating_min_display_var, 2, 0, 3000)
        self._build_slider_row(body, "Rating max", self.rating_max_var, self.rating_max_display_var, 3, 0, 3000)
        self._build_slider_row(body, "Popularity min", self.popularity_min_var, self.popularity_display_var, 4, 0, 100)
        self._build_theme_row(body)

        footer = ttk.Frame(body)
        footer.grid(row=8, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(footer, text="Import & Play", command=self._accept).pack(side=tk.RIGHT, padx=(0, 6))

        body.columnconfigure(1, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Return>", lambda _event: self._accept())
        self.bind("<Escape>", lambda _event: self.destroy())

        self._sync_slider_labels()
        self._refresh_selected_themes()

    def show_modal(self) -> LichessImportOptions | None:
        self.grab_set()
        self.wait_window()
        return self.result

    def _build_source_row(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="CSV file").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=self.csv_path_var, state="readonly", width=52).grid(
            row=0, column=1, sticky="ew", padx=(0, 8), pady=4
        )
        ttk.Button(parent, text="Browse...", command=self._browse).grid(row=0, column=2, sticky="e", pady=4)

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

    def _build_theme_row(self, parent: ttk.Frame) -> None:
        section = ttk.LabelFrame(parent, text="Themes")
        section.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(8, 4))
        section.columnconfigure(0, weight=1)

        chooser = ttk.Frame(section)
        chooser.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        chooser.columnconfigure(0, weight=1)
        ttk.Label(chooser, text="Add theme").grid(row=0, column=0, sticky="w")
        self.theme_combo = ttk.Combobox(
            chooser,
            state="readonly",
            values=sorted(LICHESS_THEMES),
            textvariable=self.theme_choice_var,
            width=24,
        )
        self.theme_combo.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(chooser, text="Add", command=self._add_theme).grid(row=1, column=1, sticky="e")

        list_frame = ttk.Frame(section)
        list_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 4))
        list_frame.columnconfigure(0, weight=1)
        self.themes_listbox = tk.Listbox(
            list_frame,
            height=7,
            selectmode=tk.EXTENDED,
            background=self._theme.field_bg,
            foreground=self._theme.field_text,
            selectbackground=self._theme.menu_active_bg,
            selectforeground=self._theme.menu_active_text,
            highlightbackground=self._theme.border,
            highlightcolor=self._theme.accent,
            relief=tk.FLAT,
            borderwidth=1,
        )
        self.themes_listbox.grid(row=0, column=0, sticky="ew")
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.themes_listbox.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.themes_listbox.configure(yscrollcommand=scroll.set)

        actions = ttk.Frame(section)
        actions.grid(row=2, column=0, sticky="w", padx=8, pady=(0, 8))
        ttk.Button(actions, text="Remove selected", command=self._remove_selected_themes).pack(side=tk.LEFT)
        ttk.Button(actions, text="Clear", command=self._clear_themes).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(actions, text="No themes selected means any theme.", style="Muted.TLabel").pack(
            side=tk.LEFT, padx=(12, 0)
        )

    def _browse(self) -> None:
        initialdir = (
            Path(self.csv_path_var.get()).expanduser().parent
            if self.csv_path_var.get().strip()
            else Path.home()
        )
        path = filedialog.askopenfilename(
            parent=self,
            title="Choose Lichess CSV",
            initialdir=str(initialdir),
            filetypes=[("CSV files", "*.csv"), ("All files", "*")],
        )
        if path:
            self.csv_path_var.set(path)

    def _add_theme(self) -> None:
        theme = self.theme_choice_var.get().strip()
        if not theme or theme not in LICHESS_THEMES:
            return
        if theme not in self._selected_themes:
            self._selected_themes.append(theme)
            self._refresh_selected_themes()

    def _remove_selected_themes(self) -> None:
        selected_indices = list(self.themes_listbox.curselection())
        if not selected_indices:
            return
        for index in reversed(selected_indices):
            del self._selected_themes[index]
        self._refresh_selected_themes()

    def _clear_themes(self) -> None:
        self._selected_themes.clear()
        self._refresh_selected_themes()

    def _refresh_selected_themes(self) -> None:
        self.themes_listbox.delete(0, tk.END)
        for theme in self._selected_themes:
            self.themes_listbox.insert(tk.END, theme)

    def _sync_slider_labels(self) -> None:
        self.rating_min_display_var.set(str(round(self.rating_min_var.get())))
        self.rating_max_display_var.set(str(round(self.rating_max_var.get())))
        self.popularity_display_var.set(str(round(self.popularity_min_var.get())))

    def _update_slider_label(self, display_var: tk.StringVar, value: str) -> None:
        display_var.set(str(round(float(value))))

    def _theme_choice_default(self) -> str:
        if self._settings.themes:
            for theme in self._settings.themes:
                if theme in LICHESS_THEMES:
                    return theme
        return sorted(LICHESS_THEMES)[0]

    def _accept(self) -> None:
        csv_path_text = self.csv_path_var.get().strip()
        if not csv_path_text:
            messagebox.showerror("Missing CSV file", "Choose a Lichess CSV file first.", parent=self)
            return
        csv_path = Path(csv_path_text).expanduser()
        if not csv_path.exists():
            messagebox.showerror("Missing CSV file", "The selected CSV file does not exist.", parent=self)
            return
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
            csv_path=csv_path,
            sample_size=sample_size,
            rating_min=rating_min,
            rating_max=rating_max,
            popularity_min=popularity_min,
            themes=tuple(self._selected_themes),
        )
        self.destroy()
