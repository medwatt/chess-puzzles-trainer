from __future__ import annotations

import sqlite3
import tkinter as tk
from tkinter import ttk

from chess_puzzles.reports import AttemptSummary, attempt_summary, format_duration_ms


class StatisticsDialog(tk.Toplevel):
    """Basic all-time attempt statistics.

    Deliberately minimal: it renders rows from a single AttemptSummary. To add
    more (date ranges, per-theme breakdown, ...), add queries and append more
    sections here -- nothing else in the app depends on this layout.
    """

    def __init__(self, parent: tk.Misc, connection: sqlite3.Connection) -> None:
        super().__init__(parent, name="statistics", class_="ChessPuzzlesStatistics")
        self.title("Statistics")
        self.transient(parent)
        self.resizable(False, False)

        summary = attempt_summary(connection)
        self._build_section("All time", summary)

        footer = ttk.Frame(self)
        footer.pack(fill=tk.X, padx=12, pady=(8, 12))
        ttk.Button(footer, text="Close", command=self.destroy).pack(side=tk.RIGHT)
        self.bind("<Escape>", lambda _event: self.destroy())

    def _build_section(self, heading: str, summary: AttemptSummary) -> None:
        section = ttk.LabelFrame(self, text=heading, padding=(12, 8))
        section.pack(fill=tk.X, padx=12, pady=(12, 0))
        rows = _summary_rows(summary)
        for row, (label, value) in enumerate(rows):
            ttk.Label(section, text=f"{label}:").grid(row=row, column=0, sticky="w", padx=(0, 12), pady=1)
            ttk.Label(section, text=value).grid(row=row, column=1, sticky="e", pady=1)

    def show(self) -> None:
        self.grab_set()
        self.wait_window()


def _summary_rows(summary: AttemptSummary) -> list[tuple[str, str]]:
    solved = str(summary.solved)
    if summary.solved_percent is not None:
        solved = f"{summary.solved} ({summary.solved_percent}%)"
    return [
        ("Attempted", str(summary.attempted)),
        ("Solved", solved),
        ("Gave up", str(summary.gave_up)),
        ("Total time", format_duration_ms(summary.total_ms)),
        ("Average time", format_duration_ms(summary.avg_ms)),
    ]
