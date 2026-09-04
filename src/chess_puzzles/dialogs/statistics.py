from __future__ import annotations

import sqlite3
import tkinter as tk
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tkinter import ttk

from chess_puzzles.constants import STATISTICS_DIALOG_GEOMETRY
from chess_puzzles.reports import AttemptSummary, attempt_summary, deck_summaries, format_duration_ms
from chess_puzzles.ui.modal import ModalParent, run_modal
from chess_puzzles.ui.table import autosize_columns
from chess_puzzles.ui.window import fit_window
from chess_puzzles.vision.registry import registry
from chess_puzzles.vision.stats import vision_summary


class StatisticsDialog(tk.Toplevel):
    def __init__(self, parent: ModalParent, connection: sqlite3.Connection) -> None:
        super().__init__(parent, name="statistics", class_="ChessPuzzlesStatistics")
        self.title("Training Statistics")
        self.transient(parent)

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 6))
        notebook.add(self._overview(notebook, connection), text="Overview")
        notebook.add(self._decks(notebook, connection), text="Decks")
        notebook.add(self._vision(notebook, connection), text="Vision")
        footer = ttk.Frame(self)
        footer.pack(fill=tk.X, padx=12, pady=(6, 12))
        ttk.Button(footer, text="Close", command=self.destroy).pack(side=tk.RIGHT)
        self.bind("<Escape>", lambda _event: self.destroy())
        fit_window(self, STATISTICS_DIALOG_GEOMETRY)

    def _overview(self, parent: ttk.Notebook, connection: sqlite3.Connection) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=12)
        periods = (("Last 7 days", 7), ("Last 30 days", 30), ("All time", None))
        summaries: list[AttemptSummary] = []
        for _heading, days in periods:
            since = None
            if days is not None:
                since = (datetime.now(UTC) - timedelta(days=days)).isoformat().replace("+00:00", "Z")
            summaries.append(attempt_summary(connection, since=since))

        rows = [_summary_rows(summary) for summary in summaries]
        tree = _tree(
            frame,
            (
                ("metric", "Metric"),
                ("week", "Last 7 days"),
                ("month", "Last 30 days"),
                ("all", "All time"),
            ),
        )
        for index, (label, _value) in enumerate(rows[0]):
            tree.insert("", "end", values=(label, *(summary[index][1] for summary in rows)))
        autosize_columns(tree)
        tree.pack(fill=tk.BOTH, expand=True)
        return frame

    def _decks(self, parent: ttk.Notebook, connection: sqlite3.Connection) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=12)
        tree = _tree(frame, (
            ("deck", "Deck"), ("attempts", "Attempts"), ("clean", "Clean"),
            ("mistakes", "Mistakes"), ("aids", "Aids"), ("time", "Time"),
        ))
        for summary in deck_summaries(connection):
            name = summary.name or (Path(summary.database_path).stem if summary.database_path else "Unknown course")
            tree.insert("", "end", values=(name, summary.attempted, summary.clean_solves,
                        summary.mistakes, summary.aids, format_duration_ms(summary.total_ms)))
        autosize_columns(tree)
        tree.pack(fill=tk.BOTH, expand=True)
        return frame

    def _vision(self, parent: ttk.Notebook, connection: sqlite3.Connection) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=12)
        tree = _tree(frame, (("drill", "Drill"), ("trials", "Trials"),
                             ("accuracy", "Exact accuracy"), ("average", "Average")))
        names = {drill.id: drill.name for drill in registry.all()}
        drill_ids = [row[0] for row in connection.execute(
            "SELECT drill_id FROM vision_attempt GROUP BY drill_id ORDER BY MAX(at) DESC"
        )]
        for drill_id in drill_ids:
            summary = vision_summary(connection, drill_id=drill_id)
            tree.insert("", "end", values=(names.get(drill_id, drill_id), summary.trials,
                        f"{summary.accuracy_percent:.0f}%", format_duration_ms(summary.average_ms)))
        autosize_columns(tree)
        tree.pack(fill=tk.BOTH, expand=True)
        return frame

    def show(self) -> None:
        run_modal(self)


def _tree(parent: tk.Misc, columns: tuple[tuple[str, str], ...]) -> ttk.Treeview:
    names = tuple(column[0] for column in columns)
    tree = ttk.Treeview(parent, columns=names, show="headings")
    for name, label in columns:
        tree.heading(name, text=label)
        tree.column(name, anchor="w")
    return tree


def _summary_rows(summary: AttemptSummary) -> list[tuple[str, str]]:
    solved = str(summary.solved)
    if summary.solved_percent is not None:
        solved = f"{summary.solved} ({summary.solved_percent}%)"
    return [
        ("Attempted", str(summary.attempted)), ("Solved", solved),
        ("Gave up", str(summary.gave_up)), ("Total time", format_duration_ms(summary.total_ms)),
        ("Average time", format_duration_ms(summary.avg_ms)),
    ]
