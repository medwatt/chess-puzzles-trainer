from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, replace
from pathlib import Path
from tkinter import messagebox, ttk

from chess_puzzles.lichess.filters import (
    FILTER_TABS,
    NUMERIC_FILTERS,
    TAB_OPENINGS,
    TAB_THEMES,
    NumericFilter,
    filters_for,
)
from chess_puzzles.lichess.importer import (
    THEME_MODE_ALL,
    THEME_MODE_ANY,
    LichessImportCriteria,
)
from chess_puzzles.lichess.settings import LichessImportSettings, load_lichess_settings
from chess_puzzles.lichess.vocabulary import LICHESS_OPENINGS, LICHESS_THEMES
from chess_puzzles.settings.theme_repository import UiTheme
from chess_puzzles.ui.modal import ModalParent, run_modal
from chess_puzzles.ui.theme_selector import ThemeSelector


# Min/max fields that must not cross. One entry per range; extending the
# NUMERIC_FILTERS table with a new pair means adding one line here.
RANGE_PAIRS = (
    ("rating_min", "rating_max", "rating"),
    ("moves_min", "moves_max", "move count"),
)


@dataclass(slots=True, frozen=True)
class LichessImportOptions:
    """What the dialog produced: a CSV to read and the filters to read it with.

    The filter values live in the settings object rather than being restated
    here, so a new filter reaches the importer without another copy of every
    field."""

    csv_path: Path
    settings: LichessImportSettings

    def to_criteria(self) -> LichessImportCriteria:
        return LichessImportCriteria(
            sample_size=self.settings.sample_size,
            themes=self.settings.themes,
            theme_mode=self.settings.theme_mode,
            themes_excluded=self.settings.themes_excluded,
            openings=self.settings.openings,
            **{item.field: getattr(self.settings, item.field) for item in NUMERIC_FILTERS},
        )

    def to_settings(self) -> LichessImportSettings:
        return self.settings


class LichessImportDialog(tk.Toplevel):
    """Collect filter options for a one-shot Lichess import.

    Filters are grouped into notebook tabs because they answer different
    questions -- how hard, how well-vetted, what is in it -- and because a
    single column would run off the screen as filters are added. Sliders are
    built from the NUMERIC_FILTERS table, so a new filter appears here by
    declaring it there.

    ``csv_path`` is the app-wide Lichess CSV (Settings > Paths), resolved by
    the caller; the dialog only displays it."""

    def __init__(
        self,
        parent: ModalParent,
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
        self.theme_mode_var = tk.StringVar(value=self._settings.theme_mode)
        # ttk.Scale writes fractional positions, so these are DoubleVars and
        # every reader rounds.
        self._value_vars: dict[str, tk.DoubleVar] = {}
        self._display_vars: dict[str, tk.StringVar] = {}
        for item in NUMERIC_FILTERS:
            current = getattr(self._settings, item.field)
            self._value_vars[item.field] = tk.DoubleVar(value=current)
            self._display_vars[item.field] = tk.StringVar(value=str(current))

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)
        self._build_source_row(body)
        self._build_sample_row(body)

        notebook = ttk.Notebook(body)
        notebook.grid(row=2, column=0, columnspan=3, sticky="nsew", pady=(10, 4))
        self._tabs = {name: ttk.Frame(notebook, padding=10) for name in FILTER_TABS}
        for name in FILTER_TABS:
            notebook.add(self._tabs[name], text=name)
            self._tabs[name].columnconfigure(0, weight=1)

        for name in FILTER_TABS:
            for row, item in enumerate(filters_for(name)):
                self._build_slider_row(self._tabs[name], item, row)
        self._build_themes_tab(self._tabs[TAB_THEMES], theme)
        self._build_openings_tab(self._tabs[TAB_OPENINGS], theme)

        footer = ttk.Frame(body)
        footer.grid(row=3, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(footer, text="Import & Play", command=self._accept).pack(side=tk.RIGHT, padx=(0, 6))

        body.columnconfigure(1, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Return>", lambda _event: self._accept())
        self.bind("<Escape>", lambda _event: self.destroy())

    def show_modal(self) -> LichessImportOptions | None:
        run_modal(self)
        return self.result

    def _build_source_row(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Puzzles from").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Label(parent, text=self._csv_path.name, style="Muted.TLabel").grid(
            row=0, column=1, sticky="w", padx=(0, 8), pady=4
        )

    def _build_sample_row(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="Number of puzzles").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(parent, textvariable=self.sample_size_var, width=18).grid(
            row=1, column=1, sticky="w", pady=4
        )

    def _build_slider_row(self, parent: ttk.Frame, item: NumericFilter, row: int) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky="ew", pady=4)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text=item.label, width=20).grid(row=0, column=0, sticky="w")
        display_var = self._display_vars[item.field]
        ttk.Scale(
            frame,
            from_=item.minimum,
            to=item.maximum,
            orient=tk.HORIZONTAL,
            variable=self._value_vars[item.field],
            command=lambda value, var=display_var: var.set(str(round(float(value)))),
            length=320,
        ).grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Label(frame, textvariable=display_var, width=7, anchor=tk.E).grid(
            row=0, column=2, sticky="e"
        )
        if item.hint:
            ttk.Label(frame, text=item.hint, style="Muted.TLabel").grid(
                row=1, column=1, columnspan=2, sticky="w", padx=(8, 0)
            )

    def _build_themes_tab(self, parent: ttk.Frame, theme: UiTheme) -> None:
        mode = ttk.Frame(parent)
        mode.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        ttk.Label(mode, text="Match").pack(side=tk.LEFT)
        ttk.Radiobutton(
            mode, text="any selected theme", value=THEME_MODE_ANY, variable=self.theme_mode_var
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Radiobutton(
            mode, text="all selected themes", value=THEME_MODE_ALL, variable=self.theme_mode_var
        ).pack(side=tk.LEFT, padx=(8, 0))
        self.theme_selector = ThemeSelector(
            parent, theme, LICHESS_THEMES, title="Include", noun="theme",
            selected=self._settings.themes, height=4,
        )
        self.theme_selector.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        self.theme_exclude_selector = ThemeSelector(
            parent, theme, LICHESS_THEMES, title="Exclude", noun="excluded theme",
            selected=self._settings.themes_excluded, height=4,
        )
        self.theme_exclude_selector.grid(row=2, column=0, sticky="ew")

    def _build_openings_tab(self, parent: ttk.Frame, theme: UiTheme) -> None:
        self.opening_selector = ThemeSelector(
            parent, theme, LICHESS_OPENINGS, title="Openings", noun="opening",
            selected=self._settings.openings, height=8,
        )
        self.opening_selector.grid(row=0, column=0, sticky="ew")

    def _numeric_values(self) -> dict[str, int]:
        return {field: round(var.get()) for field, var in self._value_vars.items()}

    def _accept(self) -> None:
        try:
            sample_size = int(self.sample_size_var.get().strip())
        except ValueError:
            sample_size = 0
        if sample_size <= 0:
            messagebox.showerror(
                "Invalid sample size", "Number of puzzles must be a positive integer.", parent=self
            )
            return
        values = self._numeric_values()
        for low, high, label in RANGE_PAIRS:
            if values[low] > values[high]:
                messagebox.showerror(
                    "Invalid range",
                    f"The {label} minimum must be less than or equal to the maximum.",
                    parent=self,
                )
                return
        self.result = LichessImportOptions(
            csv_path=self._csv_path,
            settings=replace(
                self._settings,
                sample_size=sample_size,
                themes=self.theme_selector.selected,
                theme_mode=self.theme_mode_var.get(),
                themes_excluded=self.theme_exclude_selector.selected,
                openings=self.opening_selector.selected,
                **values,
            ),
        )
        self.destroy()
