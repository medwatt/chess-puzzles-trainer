from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Literal, Sequence

from chess_puzzles.ui.modal import run_modal


@dataclass(frozen=True, slots=True)
class PathField:
    """One user-configurable path in the Paths dialog.

    To add a new path setting, add one PathField to the call site and one
    key to AppSettings. The dialog handles the rest.
    """

    key: str
    label: str
    description: str
    value: str = ""
    kind: Literal["directory", "file"] = "directory"
    filetypes: tuple[tuple[str, str], ...] = field(default_factory=tuple)


class PathsDialog(tk.Toplevel):
    """Edit every user-configurable path in one place."""

    def __init__(self, parent: tk.Misc, fields: Sequence[PathField]) -> None:
        super().__init__(parent, name="paths", class_="ChessPuzzlesPaths")
        self.title("Paths")
        self.transient(parent)
        self.resizable(False, False)
        self.result: dict[str, str] | None = None
        self._fields = tuple(fields)
        self._vars: dict[str, tk.StringVar] = {}

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(1, weight=1)

        row = 0
        for path_field in self._fields:
            variable = tk.StringVar(value=path_field.value)
            self._vars[path_field.key] = variable
            ttk.Label(body, text=path_field.label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=(6, 0))
            ttk.Entry(body, textvariable=variable, width=52).grid(row=row, column=1, sticky="ew", pady=(6, 0))
            ttk.Button(
                body,
                text="Browse...",
                command=lambda var=variable, f=path_field: self._browse(var, f),
                takefocus=False,
            ).grid(row=row, column=2, sticky="e", padx=(8, 0), pady=(6, 0))
            ttk.Button(
                body,
                text="Clear",
                command=lambda var=variable: var.set(""),
                takefocus=False,
            ).grid(row=row, column=3, sticky="e", padx=(4, 0), pady=(6, 0))
            row += 1
            ttk.Label(body, text=path_field.description, style="Muted.TLabel", wraplength=520, justify=tk.LEFT).grid(
                row=row, column=1, columnspan=3, sticky="w", pady=(2, 6)
            )
            row += 1

        footer = ttk.Frame(body)
        footer.grid(row=row, column=0, columnspan=4, sticky="e", pady=(10, 0))
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(footer, text="Save", command=self._accept).pack(side=tk.RIGHT, padx=(0, 6))

        self.bind("<Return>", lambda _event: self._accept())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def show_modal(self) -> dict[str, str] | None:
        run_modal(self)
        return self.result

    def _browse(self, variable: tk.StringVar, path_field: PathField) -> None:
        current = Path(variable.get().strip()).expanduser() if variable.get().strip() else None
        if path_field.kind == "file":
            initialdir = current.parent if current is not None and current.parent.is_dir() else Path.home()
            path = filedialog.askopenfilename(
                parent=self,
                title=path_field.label,
                initialdir=str(initialdir),
                filetypes=list(path_field.filetypes) or [("All files", "*")],
            )
        else:
            initialdir = current if current is not None and current.is_dir() else Path.home()
            path = filedialog.askdirectory(parent=self, title=path_field.label, initialdir=str(initialdir))
        if path:
            variable.set(path)

    def _accept(self) -> None:
        # Empty string means unset. Non-empty paths are normalized but
        # do not need to exist (a pieces folder on a removable drive
        # might be offline).
        self.result = {
            key: str(Path(value).expanduser()) if (value := variable.get().strip()) else ""
            for key, variable in self._vars.items()
        }
        self.destroy()
