from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Mapping

from chess_puzzles.settings.options import (
    OPTIONS,
    SECTION_NOTES,
    SECTIONS,
    Option,
    options_in,
)
from chess_puzzles.ui.modal import run_modal


class OptionsDialog(tk.Toplevel):
    """Edit every preference in one place, one tab per section.

    Rendered entirely from ``settings.options``: to add a preference, add a
    row there, and to add a tab, add a section. ``deck_kind`` is the kind of
    the open course; rows that do not apply to it are greyed rather than
    hidden -- so a preference never disappears from where the user last saw
    it -- and the section's note says why, once, above them.
    """

    def __init__(
        self, parent: tk.Misc, values: Mapping[str, bool], *, deck_kind: str | None = None
    ) -> None:
        super().__init__(parent, name="options", class_="ChessPuzzlesOptions")
        self.title("Options")
        self.transient(parent)
        self.resizable(False, False)
        self.result: dict[str, bool] | None = None
        self._vars: dict[str, tk.BooleanVar] = {}

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        notebook = ttk.Notebook(body)
        notebook.pack(fill=tk.BOTH, expand=True)
        for section in SECTIONS:
            options = options_in(section)
            if not options:
                continue
            page = ttk.Frame(notebook, padding=(12, 10))
            page.columnconfigure(0, weight=1)
            notebook.add(page, text=section)
            row = 0
            note = SECTION_NOTES.get(section)
            if note is not None and not all(o.applies_to(deck_kind) for o in options):
                ttk.Label(
                    page, text=note, style="Muted.TLabel", wraplength=420, justify=tk.LEFT
                ).grid(row=0, column=0, sticky="w", pady=(0, 8))
                row = 1
            for offset, option in enumerate(options):
                self._build_option(page, row + offset, option, values[option.key], deck_kind)

        footer = ttk.Frame(body)
        footer.pack(fill=tk.X, pady=(10, 0))
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(footer, text="Save", command=self._accept).pack(side=tk.RIGHT, padx=(0, 6))

        self.bind("<Return>", lambda _event: self._accept())
        self.bind("<Escape>", lambda _event: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def show_modal(self) -> dict[str, bool] | None:
        run_modal(self)
        return self.result

    def _build_option(
        self,
        page: ttk.Frame,
        row: int,
        option: Option,
        value: bool,
        deck_kind: str | None,
    ) -> None:
        applies = option.applies_to(deck_kind)
        container = ttk.Frame(page)
        container.grid(row=row, column=0, sticky="ew", pady=(0, 8))
        container.columnconfigure(0, weight=1)

        variable = tk.BooleanVar(value=bool(value))
        ttk.Checkbutton(
            container,
            text=option.label,
            variable=variable,
            state=tk.NORMAL if applies else tk.DISABLED,
            takefocus=False,
        ).grid(row=0, column=0, sticky="w")
        self._vars[option.key] = variable
        # Why a row is greyed is stated once per section, not per row.
        ttk.Label(
            container,
            text=option.help,
            style="Muted.TLabel",
            wraplength=420,
            justify=tk.LEFT,
        ).grid(row=1, column=0, sticky="w", padx=(20, 0))

    def _accept(self) -> None:
        # Out-of-scope rows are still returned at their stored value: greying
        # a row must not silently rewrite the preference behind it.
        self.result = {option.key: self._vars[option.key].get() for option in OPTIONS}
        self.destroy()
