from __future__ import annotations

import sqlite3
import tkinter as tk
from typing import Literal
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

from chess_puzzles.arena.service import ArenaSummary, list_sessions
from chess_puzzles.ui.table import autosize_columns
from chess_puzzles.ui.modal import ModalParent, run_modal


class ArenaSessionsDialog(tk.Toplevel):
    """Browse, resume, and delete rated sessions.

    Sessions deliberately live outside the Course Library (they are training
    records, not courses); this dialog is their one management surface. Every
    number shown is derived live from the session files and the attempt log.

    ``show()`` returns the path of the session to open, or None.
    """

    COLUMNS = ("session", "started", "rating", "puzzles", "attempted", "themes")

    def __init__(
        self,
        parent: ModalParent,
        conn: sqlite3.Connection,
        *,
        open_path: Path | None = None,
    ) -> None:
        super().__init__(parent, name="arenasessions", class_="ChessPuzzlesArenaSessions")
        self.title("Rated Sessions")
        self.transient(parent)
        self.result: Path | None = None
        self._conn = conn
        # The session currently open in the main window cannot be deleted.
        self._open_path = open_path.resolve() if open_path is not None else None
        self._summaries: dict[str, ArenaSummary] = {}

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        table_frame = ttk.Frame(body)
        table_frame.pack(fill=tk.BOTH, expand=True)
        self._table = ttk.Treeview(
            table_frame, columns=self.COLUMNS, show="headings", selectmode="browse", height=10
        )
        # Literals rather than tk.W / tk.E: tkinter declares those constants as
        # plain str, which the heading/column signatures do not accept.
        headings: dict[str, tuple[str, Literal["w", "e"]]] = {
            "session": ("Session", "w"),
            "started": ("Started", "w"),
            "rating": ("Rating", "e"),
            "puzzles": ("Puzzles", "e"),
            "attempted": ("Attempted", "e"),
            "themes": ("Themes", "w"),
        }
        for column, (heading, anchor) in headings.items():
            self._table.heading(column, text=heading, anchor=anchor)
            self._table.column(column, anchor=anchor, stretch=column in {"session", "themes"})
        scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self._table.yview)
        self._table.configure(yscrollcommand=scroll.set)
        self._table.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        table_frame.columnconfigure(0, weight=1)
        table_frame.rowconfigure(0, weight=1)
        self._table.bind("<Double-1>", lambda _event: self._open_selected())

        footer = ttk.Frame(body)
        footer.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(footer, text="Delete...", command=self._delete_selected).pack(side=tk.LEFT)
        ttk.Button(footer, text="Close", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(footer, text="Open", command=self._open_selected).pack(
            side=tk.RIGHT, padx=(0, 6)
        )

        self.bind("<Return>", lambda _event: self._open_selected())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._populate()

    def show(self) -> Path | None:
        run_modal(self)
        return self.result

    def _populate(self) -> None:
        self._table.delete(*self._table.get_children())
        self._summaries = {}
        for summary in list_sessions(self._conn):
            row_id = str(summary.path)
            self._summaries[row_id] = summary
            rating = str(summary.rating)
            if summary.rating != summary.start_rating:
                rating = f"{summary.rating} ({summary.rating - summary.start_rating:+d})"
            self._table.insert(
                "",
                tk.END,
                iid=row_id,
                values=(
                    summary.name,
                    self._local_time(summary.created_at),
                    rating,
                    summary.puzzle_count,
                    summary.attempted,
                    ", ".join(summary.themes) or "any",
                ),
            )
        children = self._table.get_children()
        if children:
            self._table.selection_set(children[0])
        autosize_columns(self._table)

    @staticmethod
    def _local_time(created_at: str) -> str:
        # created_at is stored as UTC ISO (store/clock.now_iso); show local.
        try:
            when = datetime.fromisoformat(created_at)
        except ValueError:
            return created_at[:16].replace("T", " ")
        return when.astimezone().strftime("%Y-%m-%d %H:%M")

    def _selected(self) -> ArenaSummary | None:
        selection = self._table.selection()
        return self._summaries.get(selection[0]) if selection else None

    def _open_selected(self) -> None:
        summary = self._selected()
        if summary is None:
            return
        self.result = summary.path
        self.destroy()

    def _delete_selected(self) -> None:
        summary = self._selected()
        if summary is None:
            return
        if self._open_path is not None and summary.path.resolve() == self._open_path:
            messagebox.showinfo(
                "Session is open",
                "This session is open in the main window; open another deck first.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Delete rated session",
            f"Delete '{summary.name}' ({summary.attempted} attempted puzzle(s))?\n\n"
            "Its puzzles will no longer be available to the review queue."
            " Your attempt history is kept.",
            parent=self,
        ):
            return
        try:
            summary.path.unlink()
        except OSError as exc:
            messagebox.showerror("Could not delete session", str(exc), parent=self)
            return
        self._populate()
