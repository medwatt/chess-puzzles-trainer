from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Sequence


@dataclass(frozen=True, slots=True)
class FolderField:
    """One user-configurable folder in the Folders dialog.

    To add a new folder setting, add one FolderField to the call site
    and one key to AppSettings. The dialog handles the rest.
    """

    key: str
    label: str
    description: str
    value: str = ""


class FoldersDialog(tk.Toplevel):
    """Edit the app's user-configurable folders in one place."""

    def __init__(self, parent: tk.Misc, fields: Sequence[FolderField]) -> None:
        super().__init__(parent, name="folders", class_="ChessPuzzlesFolders")
        self.title("Folders")
        self.transient(parent)
        self.resizable(False, False)
        self.result: dict[str, str] | None = None
        self._fields = tuple(fields)
        self._vars: dict[str, tk.StringVar] = {}

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(1, weight=1)

        row = 0
        for field in self._fields:
            variable = tk.StringVar(value=field.value)
            self._vars[field.key] = variable
            ttk.Label(body, text=field.label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=(6, 0))
            ttk.Entry(body, textvariable=variable, width=52).grid(row=row, column=1, sticky="ew", pady=(6, 0))
            ttk.Button(
                body,
                text="Browse...",
                command=lambda var=variable, label=field.label: self._browse(var, label),
                takefocus=False,
            ).grid(row=row, column=2, sticky="e", padx=(8, 0), pady=(6, 0))
            ttk.Button(
                body,
                text="Clear",
                command=lambda var=variable: var.set(""),
                takefocus=False,
            ).grid(row=row, column=3, sticky="e", padx=(4, 0), pady=(6, 0))
            row += 1
            ttk.Label(body, text=field.description, style="Muted.TLabel", wraplength=520, justify=tk.LEFT).grid(
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
        self.grab_set()
        self.wait_window()
        return self.result

    def _browse(self, variable: tk.StringVar, label: str) -> None:
        current = variable.get().strip()
        initialdir = current if current and Path(current).expanduser().is_dir() else str(Path.home())
        path = filedialog.askdirectory(parent=self, title=label, initialdir=initialdir)
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
