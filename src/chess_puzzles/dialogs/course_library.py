"""Searchable course chooser backed by the persistent library index."""

from __future__ import annotations

import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk

from chess_puzzles.dialogs.choice import ChoiceDialog
from chess_puzzles.review import due_reviews
from chess_puzzles.store import CourseLibrary, LibraryCourse


class CourseLibraryDialog(tk.Toplevel):
    COLUMNS = ("course", "type", "status", "tags", "puzzles", "attempts", "due")

    def __init__(self, parent: tk.Misc, library: CourseLibrary, connection: sqlite3.Connection) -> None:
        super().__init__(parent, name="courselibrary", class_="ChessPuzzlesCourseLibrary")
        self.title("Course Library")
        self.transient(parent)
        self.geometry("1050x620")
        self.minsize(760, 440)
        self._library = library
        self._connection = connection
        self.result: Path | None = None
        self._courses: dict[str, LibraryCourse] = {}
        self._attempts: dict[str, int] = {}
        self._due: dict[str, int] = {}
        self._sort_column = "course"
        self._sort_descending = False

        toolbar = ttk.Frame(self, padding=(12, 12, 12, 6))
        toolbar.pack(fill=tk.X)
        ttk.Label(toolbar, text="Search").pack(side=tk.LEFT)
        self._search = tk.StringVar()
        search = ttk.Entry(toolbar, textvariable=self._search, width=36)
        search.pack(side=tk.LEFT, padx=(8, 12), fill=tk.X, expand=True)
        self._search.trace_add("write", lambda *_args: self._populate())
        ttk.Button(toolbar, text="Rescan", command=self._rescan).pack(side=tk.RIGHT)

        table_frame = ttk.Frame(self, padding=(12, 6))
        table_frame.pack(fill=tk.BOTH, expand=True)
        self._table = ttk.Treeview(table_frame, columns=self.COLUMNS, show="headings", selectmode="browse")
        headings = {
            "course": ("Course", 300), "type": ("Type", 110), "status": ("Status", 95), "tags": ("Tags", 140),
            "puzzles": ("Puzzles", 80), "attempts": ("Attempts", 100), "due": ("Due", 65),
        }
        for column, (label, width) in headings.items():
            self._table.heading(column, text=label, command=lambda value=column: self._sort(value))
            self._table.column(column, width=width, minwidth=55, stretch=column == "course")
        y_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self._table.yview)
        x_scroll = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self._table.xview)
        self._table.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self._table.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self._table.bind("<Double-1>", lambda _event: self._open())
        self._table.bind("<Return>", lambda _event: self._open())
        self._table.bind("<<TreeviewSelect>>", lambda _event: self._update_detail())

        self._status = tk.StringVar()
        self._detail = tk.StringVar(value="Select a course to see its location.")
        ttk.Label(self, textvariable=self._detail, style="Muted.TLabel").pack(
            fill=tk.X, padx=14, pady=(2, 0)
        )
        ttk.Label(self, textvariable=self._status, style="Muted.TLabel").pack(
            fill=tk.X, padx=14, pady=(2, 0)
        )
        footer = ttk.Frame(self, padding=(12, 6, 12, 12))
        footer.pack(fill=tk.X)
        ttk.Button(footer, text="Close", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(footer, text="Open", command=self._open).pack(side=tk.RIGHT, padx=(0, 6))
        ttk.Button(footer, text="Pin / unpin", command=self._toggle_pin).pack(side=tk.LEFT)
        ttk.Button(footer, text="Status...", command=self._set_status).pack(side=tk.LEFT, padx=(6, 0))
        ttk.Button(footer, text="Tags...", command=self._edit_tags).pack(side=tk.LEFT, padx=(6, 0))
        self.bind("<Escape>", lambda _event: self.destroy())
        search.focus_set()
        self._populate()
        self.after_idle(self._rescan)

    def show(self) -> Path | None:
        self.grab_set()
        self.wait_window()
        return self.result

    def _statistics(self) -> tuple[dict[str, int], dict[str, int]]:
        attempts = {
            row["database_id"]: row["count"]
            for row in self._connection.execute(
                "SELECT database_id,COUNT(*) AS count FROM attempt WHERE database_id<>'' GROUP BY database_id"
            )
        }
        due: dict[str, int] = {}
        for review in due_reviews(self._connection):
            if review.database_id:
                due[review.database_id] = due.get(review.database_id, 0) + 1
        return attempts, due

    def _populate(self) -> None:
        selected = self._table.selection()
        selected_id = selected[0] if selected else None
        self._table.delete(*self._table.get_children())
        attempts, due = self._statistics()
        self._attempts, self._due = attempts, due
        query = self._search.get().strip().casefold()
        courses = self._library.courses()
        self._courses = {course.database_id: course for course in courses}
        filtered = [course for course in courses if self._matches(course, query)]
        filtered.sort(key=self._sort_key, reverse=self._sort_descending)
        filtered.sort(key=lambda course: course.pinned, reverse=True)
        for course in filtered:
            marker = "* " if course.pinned else ""
            self._table.insert(
                "", "end", iid=course.database_id,
                values=(f"{marker}{course.name}", self._kind_label(course.kind), course.status.title(), ", ".join(course.tags),
                        course.puzzle_count, attempts.get(course.database_id, 0),
                        due.get(course.database_id, 0)),
            )
        if selected_id in self._table.get_children():
            self._table.selection_set(selected_id)
        self._status.set(f"{len(filtered)} of {len(courses)} course(s)")

    @staticmethod
    def _matches(course: LibraryCourse, query: str) -> bool:
        if not query:
            return True
        haystack = " ".join(
            (course.name, course.description, course.kind, course.status, course.path, *course.tags)
        )
        return query in haystack.casefold()

    def _sort_key(self, course: LibraryCourse):
        values = {
            "course": course.name.casefold(), "type": course.kind, "status": course.status, "tags": course.tags,
            "puzzles": course.puzzle_count, "attempts": self._attempts.get(course.database_id, 0),
            "due": self._due.get(course.database_id, 0),
        }
        return values.get(self._sort_column, course.name.casefold())

    def _sort(self, column: str) -> None:
        self._sort_descending = column == self._sort_column and not self._sort_descending
        self._sort_column = column
        self._populate()

    @staticmethod
    def _location_text(course: LibraryCourse) -> str:
        if not course.available:
            return "Missing"
        if course.duplicate_locations > 1:
            return f"Duplicate ({course.duplicate_locations} locations)"
        chapter_text = f" | {course.chapter_count} chapter(s)" if course.chapter_count else ""
        return f"{course.path}{chapter_text}"

    @staticmethod
    def _kind_label(kind: str) -> str:
        return "Opening" if kind == "repertoire" else kind.title()

    def _selected(self) -> LibraryCourse | None:
        selected = self._table.selection()
        return self._courses.get(selected[0]) if selected else None

    def _update_detail(self) -> None:
        course = self._selected()
        if course is None:
            self._detail.set("Select a course to see its location.")
            return
        self._detail.set(self._location_text(course))

    def _open(self) -> None:
        course = self._selected()
        if course is None:
            return
        paths = self._library.available_paths(course.database_id)
        if len(paths) > 1:
            selected = ChoiceDialog(
                self, "Choose Course File", "This course has multiple locations:",
                [str(path) for path in paths], default=str(paths[0]),
            ).show_modal()
            if selected is None:
                return
            self.result = Path(selected)
            self.destroy()
            return
        path = self._library.resolve_path(course.database_id, course.path)
        if path is None:
            messagebox.showerror(
                "Course unavailable",
                "The course file is missing. Check the database folder and rescan.",
                parent=self,
            )
            return
        self.result = path
        self.destroy()

    def _rescan(self) -> None:
        self.configure(cursor="watch")
        self.update_idletasks()
        try:
            result = self._library.scan()
        finally:
            self.configure(cursor="")
        self._populate()
        self._status.set(
            f"{result.discovered} found; {result.indexed} updated; {result.invalid} unreadable"
        )

    def _toggle_pin(self) -> None:
        course = self._selected()
        if course is not None:
            self._library.set_pinned(course.database_id, not course.pinned)
            self._populate()

    def _edit_tags(self) -> None:
        course = self._selected()
        if course is None:
            return
        value = simpledialog.askstring(
            "Course tags", "Comma-separated tags:", parent=self, initialvalue=", ".join(course.tags)
        )
        if value is not None:
            self._library.set_tags(course.database_id, value.split(","))
            self._populate()

    def _set_status(self) -> None:
        course = self._selected()
        if course is None:
            return
        value = simpledialog.askstring(
            "Course status", "Status (active, paused, completed, archived):",
            parent=self, initialvalue=course.status,
        )
        if value is None:
            return
        try:
            self._library.set_status(course.database_id, value.strip().lower())
        except ValueError:
            messagebox.showerror("Invalid status", "Use active, paused, completed, or archived.", parent=self)
            return
        self._populate()
