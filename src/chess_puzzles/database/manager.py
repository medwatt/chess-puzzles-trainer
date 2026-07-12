from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from chess_puzzles.constants import DATABASE_MANAGER_GEOMETRY
from chess_puzzles.puzzle import Puzzle
from chess_puzzles.shortcuts import MENU_ACCELERATORS, DatabaseShortcuts
from chess_puzzles.store import ContentDatabase


class DatabaseManagerDialog(tk.Toplevel):
    COLUMNS = ("index", "white", "black", "length", "parity", "skip", "theme")

    def __init__(self, parent: tk.Misc, database: ContentDatabase) -> None:
        super().__init__(parent, name="databasemanager", class_="ChessPuzzlesDatabaseManager")
        self.database = database
        self.new_name: str | None = None
        self.title(f"Course Editor - {database.meta.name}")
        self.geometry(DATABASE_MANAGER_GEOMETRY)
        self.transient(parent)
        self.accepted = False
        self.summary_var = tk.StringVar(value=self._summary_text(database.count()))
        self._sort_column: str | None = None
        self._sort_descending = False

        ttk.Label(self, textvariable=self.summary_var).pack(fill=tk.X, padx=8, pady=(8, 4))
        self._build_menu()
        self._build_table()
        self._build_footer()
        self._populate()
        self._bind_shortcuts()
        self.protocol("WM_DELETE_WINDOW", self.reject)

    def _bind_shortcuts(self) -> None:
        bindings = {
            DatabaseShortcuts.DELETE_SELECTED: self._delete_selected,
            DatabaseShortcuts.SAVE: self.accept,
            DatabaseShortcuts.CANCEL: self.reject,
            DatabaseShortcuts.SET_SELECTED_SKIP: lambda: self._set_skip_for_rows(self.table.selection(), True),
            DatabaseShortcuts.CLEAR_SELECTED_SKIP: lambda: self._set_skip_for_rows(self.table.selection(), False),
            DatabaseShortcuts.SET_SELECTED_THEME: self._set_theme_selected,
            DatabaseShortcuts.CLEAR_SELECTED_THEME: lambda: self._set_theme_selected(""),
            DatabaseShortcuts.SET_THEME_FROM_WHITE: lambda: self._set_theme_from_column("white"),
            DatabaseShortcuts.SET_THEME_FROM_BLACK: lambda: self._set_theme_from_column("black"),
        }
        for sequence, action in bindings.items():
            self.bind(sequence, lambda _event, callback=action: (callback(), "break")[1])

    def show_modal(self) -> bool:
        self.grab_set()
        self.wait_window()
        return self.accepted

    def accept(self) -> None:
        self._write_table_to_database()
        self.accepted = True
        self.destroy()

    def reject(self) -> None:
        self.accepted = False
        self.destroy()

    def _build_menu(self) -> None:
        menubar = tk.Menu(self)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Rename database...", command=self._rename_database)
        file_menu.add_separator()
        file_menu.add_command(label="Save", accelerator=MENU_ACCELERATORS[DatabaseShortcuts.SAVE], command=self.accept)
        file_menu.add_command(label="Cancel", accelerator=MENU_ACCELERATORS[DatabaseShortcuts.CANCEL], command=self.reject)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=False)
        edit_menu.add_command(
            label="Delete selected",
            accelerator=MENU_ACCELERATORS[DatabaseShortcuts.DELETE_SELECTED],
            command=self._delete_selected,
        )
        menubar.add_cascade(label="Edit", menu=edit_menu)

        skip_menu = tk.Menu(menubar, tearoff=False)
        skip_menu.add_command(label="Set all skip", command=lambda: self._set_skip_for_rows(self.table.get_children(), True))
        skip_menu.add_command(label="Clear all skip", command=lambda: self._set_skip_for_rows(self.table.get_children(), False))
        skip_menu.add_separator()
        skip_menu.add_command(
            label="Set selected skip",
            accelerator=MENU_ACCELERATORS[DatabaseShortcuts.SET_SELECTED_SKIP],
            command=lambda: self._set_skip_for_rows(self.table.selection(), True),
        )
        skip_menu.add_command(
            label="Clear selected skip",
            accelerator=MENU_ACCELERATORS[DatabaseShortcuts.CLEAR_SELECTED_SKIP],
            command=lambda: self._set_skip_for_rows(self.table.selection(), False),
        )
        menubar.add_cascade(label="Skip", menu=skip_menu)

        theme_menu = tk.Menu(menubar, tearoff=False)
        theme_menu.add_command(
            label="Set selected theme...",
            accelerator=MENU_ACCELERATORS[DatabaseShortcuts.SET_SELECTED_THEME],
            command=self._set_theme_selected,
        )
        theme_menu.add_command(
            label="Clear selected theme",
            accelerator=MENU_ACCELERATORS[DatabaseShortcuts.CLEAR_SELECTED_THEME],
            command=lambda: self._set_theme_selected(""),
        )
        theme_menu.add_separator()
        theme_menu.add_command(
            label="Set theme from White",
            accelerator=MENU_ACCELERATORS[DatabaseShortcuts.SET_THEME_FROM_WHITE],
            command=lambda: self._set_theme_from_column("white"),
        )
        theme_menu.add_command(
            label="Set theme from Black",
            accelerator=MENU_ACCELERATORS[DatabaseShortcuts.SET_THEME_FROM_BLACK],
            command=lambda: self._set_theme_from_column("black"),
        )
        menubar.add_cascade(label="Theme", menu=theme_menu)
        self.config(menu=menubar)

    def _build_table(self) -> None:
        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)
        self.table = ttk.Treeview(frame, columns=self.COLUMNS, show="headings", selectmode="extended")
        headings = {
            "index": ("Index", True),
            "white": ("White", False),
            "black": ("Black", False),
            "length": ("Length", True),
            "parity": ("Even/Odd", False),
            "skip": ("Skip first move", False),
            "theme": ("Theme", False),
        }
        for column, (heading, numeric) in headings.items():
            self.table.heading(column, text=heading, command=lambda c=column, n=numeric: self._sort_by(c, n))
            self.table.column(column, width=120, stretch=column in {"white", "black", "theme"})
        y_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.table.yview)
        self.table.configure(yscrollcommand=y_scroll.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.table.bind("<Double-1>", self._edit_clicked_cell)

    def _build_footer(self) -> None:
        footer = ttk.Frame(self)
        footer.pack(fill=tk.X, padx=8, pady=(4, 8))
        ttk.Button(footer, text="Cancel", command=self.reject).pack(side=tk.RIGHT)
        ttk.Button(footer, text="Save", command=self.accept).pack(side=tk.RIGHT, padx=(0, 6))

    def _populate(self) -> None:
        for puzzle in self.database.iter_puzzles():
            self._insert_puzzle(puzzle)
        self.summary_var.set(self._summary_text(len(self.table.get_children())))

    def _insert_puzzle(self, puzzle: Puzzle) -> None:
        self.table.insert(
            "",
            tk.END,
            iid=str(puzzle.ordinal),
            values=(
                puzzle.ordinal,
                puzzle.headers.get("White", ""),
                puzzle.headers.get("Black", ""),
                len(puzzle.moves),
                "even" if len(puzzle.moves) % 2 == 0 else "odd",
                self._skip_text(puzzle.skip_first_move),
                puzzle.theme,
            ),
        )

    def _edit_clicked_cell(self, event: tk.Event) -> None:
        row_id = self.table.identify_row(event.y)
        column_id = self.table.identify_column(event.x)
        if not row_id or not column_id:
            return
        column = self.COLUMNS[int(column_id[1:]) - 1]
        if column == "skip":
            values = list(self.table.item(row_id, "values"))
            current = values[self.COLUMNS.index("skip")] == self._skip_text(True)
            values[self.COLUMNS.index("skip")] = self._skip_text(not current)
            self.table.item(row_id, values=values)
        elif column == "theme":
            self._set_theme_for_rows([row_id])

    def _delete_selected(self) -> None:
        rows = list(self.table.selection())
        if not rows:
            return
        if not messagebox.askyesno("Delete selected puzzles", f"Delete {len(rows)} selected puzzle(s)?", parent=self):
            return
        for row_id in rows:
            self.table.delete(row_id)
        self.summary_var.set(self._summary_text(len(self.table.get_children())))

    def _rename_database(self) -> None:
        name = simpledialog.askstring("Rename database", "Database name:", parent=self, initialvalue=self.database.meta.name)
        if name is None:
            return
        name = name.strip()
        if not name:
            messagebox.showerror("Invalid database name", "Database name cannot be empty.", parent=self)
            return
        self.new_name = name
        self.title(f"Course Editor - {name}")

    def _set_skip_for_rows(self, rows: tuple[str, ...] | list[str], enabled: bool) -> None:
        for row_id in rows:
            values = list(self.table.item(row_id, "values"))
            values[self.COLUMNS.index("skip")] = self._skip_text(enabled)
            self.table.item(row_id, values=values)

    def _set_theme_selected(self, theme: str | None = None) -> None:
        self._set_theme_for_rows(list(self.table.selection()), theme)

    def _set_theme_for_rows(self, rows: list[str], theme: str | None = None) -> None:
        if not rows:
            return
        if theme is None:
            theme = simpledialog.askstring("Set theme", "Theme name:", parent=self)
            if theme is None:
                return
        for row_id in rows:
            values = list(self.table.item(row_id, "values"))
            values[self.COLUMNS.index("theme")] = theme.strip()
            self.table.item(row_id, values=values)

    def _set_theme_from_column(self, source_column: str) -> None:
        source_index = self.COLUMNS.index(source_column)
        theme_index = self.COLUMNS.index("theme")
        for row_id in self.table.selection():
            values = list(self.table.item(row_id, "values"))
            values[theme_index] = str(values[source_index]).strip()
            self.table.item(row_id, values=values)

    def _sort_by(self, column: str, numeric: bool = False) -> None:
        descending = self._sort_column == column and not self._sort_descending
        self._sort_column = column
        self._sort_descending = descending
        index = self.COLUMNS.index(column)
        rows: list[tuple[object, str]] = []
        for row_id in self.table.get_children():
            value = self.table.item(row_id, "values")[index]
            try:
                key: object = int(value) if numeric else str(value).lower()
            except (TypeError, ValueError):
                key = str(value).lower()
            rows.append((key, row_id))
        rows.sort(reverse=descending)
        for position, (_, row_id) in enumerate(rows):
            self.table.move(row_id, "", position)

    def _write_table_to_database(self) -> None:
        visible: set[int] = set()
        updates: list[tuple[int, bool, str]] = []
        for row_id in self.table.get_children():
            values = self.table.item(row_id, "values")
            ordinal = int(row_id)  # iid is ordinal
            visible.add(ordinal)
            skip = values[self.COLUMNS.index("skip")] == self._skip_text(True)
            theme = str(values[self.COLUMNS.index("theme")]).strip()
            updates.append((ordinal, skip, theme))
        all_ordinals = {puzzle.ordinal for puzzle in self.database.iter_puzzles()}
        # Apply edits before deleting: delete renumbers ordinals, which would
        # otherwise invalidate the ordinals captured above.
        self.database.update_puzzles(updates)
        self.database.delete_puzzles(all_ordinals - visible)
        if self.new_name is not None:
            self.database.set_name(self.new_name)

    def _summary_text(self, count: int) -> str:
        return f"{count} puzzles in this database"

    def _skip_text(self, enabled: bool) -> str:
        return "yes" if enabled else "no"
