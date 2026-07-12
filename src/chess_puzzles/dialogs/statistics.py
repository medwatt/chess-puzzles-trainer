from __future__ import annotations

import sqlite3
import tkinter as tk
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tkinter import ttk

from chess_puzzles.reports import AttemptSummary, attempt_summary, deck_summaries, format_duration_ms
from chess_puzzles.vision.registry import registry
from chess_puzzles.vision.stats import vision_summary


class StatisticsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, connection: sqlite3.Connection) -> None:
        super().__init__(parent, name="statistics", class_="ChessPuzzlesStatistics")
        self.title("Training Statistics")
        self.transient(parent)
        self.geometry("720x460")
        self.minsize(620, 400)

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 6))
        notebook.add(self._overview(notebook, connection), text="Overview")
        notebook.add(self._decks(notebook, connection), text="Decks")
        notebook.add(self._vision(notebook, connection), text="Vision")
        footer = ttk.Frame(self)
        footer.pack(fill=tk.X, padx=12, pady=(6, 12))
        ttk.Button(footer, text="Close", command=self.destroy).pack(side=tk.RIGHT)
        self.bind("<Escape>", lambda _event: self.destroy())

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
                ("metric", "Metric", 180),
                ("week", "Last 7 days", 140),
                ("month", "Last 30 days", 140),
                ("all", "All time", 140),
            ),
        )
        for index, (label, _value) in enumerate(rows[0]):
            tree.insert("", "end", values=(label, *(summary[index][1] for summary in rows)))
        tree.pack(fill=tk.BOTH, expand=True)
        return frame

    def _decks(self, parent: ttk.Notebook, connection: sqlite3.Connection) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=12)
        tree = _tree(frame, (
            ("deck", "Deck", 220), ("attempts", "Attempts", 75), ("clean", "Clean", 65),
            ("mistakes", "Mistakes", 70), ("aids", "Aids", 55), ("time", "Time", 90),
        ))
        for summary in deck_summaries(connection):
            name = summary.name or (Path(summary.database_path).stem if summary.database_path else "Unknown course")
            tree.insert("", "end", values=(name, summary.attempted, summary.clean_solves,
                        summary.mistakes, summary.aids, format_duration_ms(summary.total_ms)))
        tree.pack(fill=tk.BOTH, expand=True)
        return frame

    def _vision(self, parent: ttk.Notebook, connection: sqlite3.Connection) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=12)
        tree = _tree(frame, (("drill", "Drill", 280), ("trials", "Trials", 80),
                             ("accuracy", "Exact accuracy", 110), ("average", "Average", 100)))
        names = {drill.id: drill.name for drill in registry.all()}
        drill_ids = [row[0] for row in connection.execute(
            "SELECT drill_id FROM vision_attempt GROUP BY drill_id ORDER BY MAX(at) DESC"
        )]
        for drill_id in drill_ids:
            summary = vision_summary(connection, drill_id=drill_id)
            tree.insert("", "end", values=(names.get(drill_id, drill_id), summary.trials,
                        f"{summary.accuracy_percent:.0f}%", format_duration_ms(summary.average_ms)))
        tree.pack(fill=tk.BOTH, expand=True)
        return frame

    def show(self) -> None:
        self.grab_set()
        self.wait_window()


def _tree(parent: tk.Misc, columns: tuple[tuple[str, str, int], ...]) -> ttk.Treeview:
    names = tuple(column[0] for column in columns)
    tree = ttk.Treeview(parent, columns=names, show="headings")
    for name, label, width in columns:
        tree.heading(name, text=label)
        tree.column(name, width=width, anchor="w")
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
