from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from chess_puzzles.lichess.settings import load_lichess_settings
from chess_puzzles.mining.settings import (
    MiningDialogSettings,
    load_mining_settings,
)


@dataclass(slots=True, frozen=True)
class BlunderMineOptions:
    """User-selected generation parameters."""

    csv_path: Path
    count: int
    rating_min: int
    rating_max: int

    def to_settings(self) -> MiningDialogSettings:
        return MiningDialogSettings(
            csv_path=str(self.csv_path),
            count=self.count,
            rating_min=self.rating_min,
            rating_max=self.rating_max,
        )


class BlunderMineDialog(tk.Toplevel):
    """Collect parameters for generating a blunder-check deck.

    Mirrors the Lichess import dialog; the engine itself is not chosen here
    (the app's default engine is used) but is shown so a missing
    configuration is obvious before a long run starts."""

    def __init__(self, parent: tk.Misc, engine_name: str | None) -> None:
        super().__init__(parent, name="blundermine", class_="ChessPuzzlesBlunderMine")
        self.title("Generate Blunder Puzzles")
        self.transient(parent)
        self.resizable(False, False)
        self.result: BlunderMineOptions | None = None
        self._settings = load_mining_settings()

        csv_default = self._settings.csv_path or load_lichess_settings().csv_path
        self.csv_path_var = tk.StringVar(value=csv_default)
        self.count_var = tk.StringVar(value=str(self._settings.count))
        self.rating_min_var = tk.DoubleVar(value=self._settings.rating_min)
        self.rating_max_var = tk.DoubleVar(value=self._settings.rating_max)
        self.rating_min_display_var = tk.StringVar(value=str(self._settings.rating_min))
        self.rating_max_display_var = tk.StringVar(value=str(self._settings.rating_max))

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(body, text="Lichess CSV").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=self.csv_path_var, state="readonly", width=52).grid(
            row=0, column=1, sticky="ew", padx=(0, 8), pady=4
        )
        ttk.Button(body, text="Browse...", command=self._browse).grid(row=0, column=2, sticky="e", pady=4)

        ttk.Label(body, text="Number of puzzles").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(body, textvariable=self.count_var, width=18).grid(row=1, column=1, sticky="w", pady=4)

        self._build_slider_row(body, "Rating min", self.rating_min_var, self.rating_min_display_var, 2)
        self._build_slider_row(body, "Rating max", self.rating_max_var, self.rating_max_display_var, 3)

        engine_text = (
            f"Engine: {engine_name}"
            if engine_name
            else "No engine configured - set one up under Engines first."
        )
        ttk.Label(body, text=engine_text, style="Muted.TLabel").grid(
            row=4, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )

        footer = ttk.Frame(body)
        footer.grid(row=5, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
        generate = ttk.Button(footer, text="Generate", command=self._accept)
        generate.pack(side=tk.RIGHT, padx=(0, 6))
        if not engine_name:
            generate.state(["disabled"])

        body.columnconfigure(1, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Return>", lambda _event: self._accept())
        self.bind("<Escape>", lambda _event: self.destroy())

    def show_modal(self) -> BlunderMineOptions | None:
        self.grab_set()
        self.wait_window()
        return self.result

    def _build_slider_row(
        self, parent: ttk.Frame, label: str, variable: tk.DoubleVar, display_var: tk.StringVar, row: int
    ) -> None:
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=4)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text=label, width=16).grid(row=0, column=0, sticky="w")
        ttk.Scale(
            frame,
            from_=0,
            to=3000,
            orient=tk.HORIZONTAL,
            variable=variable,
            command=lambda value: display_var.set(str(round(float(value)))),
            length=340,
        ).grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Label(frame, textvariable=display_var, width=6, anchor=tk.E).grid(row=0, column=2, sticky="e")

    def _browse(self) -> None:
        current = self.csv_path_var.get().strip()
        initialdir = Path(current).expanduser().parent if current else Path.home()
        path = filedialog.askopenfilename(
            parent=self,
            title="Choose Lichess CSV",
            initialdir=str(initialdir),
            filetypes=[("CSV files", "*.csv"), ("All files", "*")],
        )
        if path:
            self.csv_path_var.set(path)

    def _accept(self) -> None:
        csv_text = self.csv_path_var.get().strip()
        if not csv_text:
            messagebox.showerror("Missing CSV file", "Choose a Lichess CSV file first.", parent=self)
            return
        csv_path = Path(csv_text).expanduser()
        if not csv_path.is_file():
            messagebox.showerror("Missing CSV file", "The selected CSV file does not exist.", parent=self)
            return
        try:
            count = int(self.count_var.get().strip())
        except ValueError:
            count = 0
        if count <= 0:
            messagebox.showerror("Invalid count", "Number of puzzles must be a positive integer.", parent=self)
            return
        rating_min = round(self.rating_min_var.get())
        rating_max = round(self.rating_max_var.get())
        if rating_min > rating_max:
            messagebox.showerror(
                "Invalid rating range", "Rating min must be less than or equal to rating max.", parent=self
            )
            return
        self.result = BlunderMineOptions(
            csv_path=csv_path, count=count, rating_min=rating_min, rating_max=rating_max
        )
        self.destroy()
