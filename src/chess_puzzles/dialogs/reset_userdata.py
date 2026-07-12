"""Scoped management of training history stored in userdata.db."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from chess_puzzles.store import UserStore
from chess_puzzles.vision.registry import registry


class UserDataManagerDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        store: UserStore,
        *,
        database_id: str | None = None,
        deck_name: str = "",
    ) -> None:
        super().__init__(parent, name="userdatamanager", class_="ChessPuzzlesUserDataManager")
        self.title("Manage User Data")
        self.transient(parent)
        self.geometry("650x430")
        self.minsize(560, 380)
        self._store = store
        self._database_id = database_id
        self.changed = False

        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 6))
        notebook.add(self._build_deck_tab(notebook, deck_name), text="Current deck")
        notebook.add(self._build_vision_tab(notebook), text="Vision drills")
        notebook.add(self._build_all_tab(notebook), text="All user data")

        footer = ttk.Frame(self)
        footer.pack(fill=tk.X, padx=12, pady=(6, 12))
        ttk.Button(footer, text="Close", command=self.destroy).pack(side=tk.RIGHT)
        self.bind("<Escape>", lambda _event: self.destroy())

    def show(self) -> bool:
        self.grab_set()
        self.wait_window()
        return self.changed

    def _build_deck_tab(self, parent: ttk.Notebook, deck_name: str) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=12)
        if self._database_id is None:
            ttk.Label(frame, text="Open a deck to manage its training data.").pack(anchor="w")
            return frame
        ttk.Label(frame, text=deck_name, font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        attempt_count = self._store.deck_attempt_count(self._database_id)
        favorite_count = self._store.deck_favorite_count(self._database_id)
        self._deck_attempts = tk.BooleanVar(value=True)
        self._deck_position = tk.BooleanVar(value=True)
        self._deck_favorites = tk.BooleanVar(value=False)
        for variable, label in (
            (self._deck_attempts, f"Solve and review history ({attempt_count} attempts)"),
            (self._deck_position, "Remembered resume position"),
            (self._deck_favorites, f"Favorites ({favorite_count})"),
        ):
            ttk.Checkbutton(frame, text=label, variable=variable).pack(anchor="w", pady=4)
        ttk.Button(frame, text="Delete selected...", command=self._delete_deck).pack(
            anchor="e", pady=(16, 0)
        )
        return frame

    def _build_vision_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=12)
        ttk.Label(frame, text="Select drill histories to delete.").pack(anchor="w", pady=(0, 8))
        columns = ("drill", "attempts", "last")
        self._vision_tree = ttk.Treeview(frame, columns=columns, show="headings", selectmode="extended")
        for column, label, width in (
            ("drill", "Drill", 270), ("attempts", "Attempts", 90), ("last", "Last activity", 170)
        ):
            self._vision_tree.heading(column, text=label)
            self._vision_tree.column(column, width=width, anchor="w")
        names = {drill.id: drill.name for drill in registry.all()}
        for history in self._store.vision_histories():
            self._vision_tree.insert(
                "", "end", iid=history.drill_id,
                values=(names.get(history.drill_id, history.drill_id), history.attempts, history.last_at[:10]),
            )
        self._vision_tree.pack(fill=tk.BOTH, expand=True)
        actions = ttk.Frame(frame)
        actions.pack(fill=tk.X, pady=(8, 0))
        ttk.Button(actions, text="Select all", command=self._select_all_vision).pack(side=tk.LEFT)
        ttk.Button(actions, text="Delete selected...", command=self._delete_vision).pack(side=tk.RIGHT)
        return frame

    def _build_all_tab(self, parent: ttk.Notebook) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=12)
        ttk.Label(frame, text="Delete all training records from this application.",
                  font=("TkDefaultFont", 11, "bold")).pack(anchor="w")
        ttk.Label(
            frame,
            text=("This includes attempts, review history, favorites, notes, resume positions, "
                  "vision history, and Course Library organization. "
                  "Application preferences and course files are preserved."),
            wraplength=560,
        ).pack(anchor="w", pady=(8, 16))
        ttk.Button(frame, text="Delete all user data...", command=self._delete_all).pack(anchor="e")
        return frame

    def _delete_deck(self) -> None:
        assert self._database_id is not None
        selected = {
            "attempts": bool(self._deck_attempts.get()),
            "favorites": bool(self._deck_favorites.get()),
            "position": bool(self._deck_position.get()),
        }
        if not any(selected.values()) or not messagebox.askyesno(
            "Delete deck data", "Delete the selected data for this deck? This cannot be undone.", parent=self
        ):
            return
        self._store.delete_deck_data(self._database_id, **selected)
        self.changed = True
        self.destroy()

    def _select_all_vision(self) -> None:
        self._vision_tree.selection_set(self._vision_tree.get_children())

    def _delete_vision(self) -> None:
        drill_ids = set(self._vision_tree.selection())
        if not drill_ids or not messagebox.askyesno(
            "Delete vision history", f"Delete history for {len(drill_ids)} selected drill(s)?", parent=self
        ):
            return
        self._store.delete_vision_attempts(drill_ids)
        for drill_id in drill_ids:
            self._vision_tree.delete(drill_id)
        self.changed = True

    def _delete_all(self) -> None:
        if not messagebox.askyesno(
            "Delete all user data",
            "Delete all training data, favorites, notes, resume positions, and vision history?\n\n"
            "Application preferences and deck files will be preserved. This cannot be undone.",
            parent=self,
        ):
            return
        self._store.delete_all_training_data()
        self.changed = True
        self.destroy()
