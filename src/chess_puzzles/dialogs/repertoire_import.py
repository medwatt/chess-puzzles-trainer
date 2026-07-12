"""Confirm how an opening course PGN should be imported.

The heuristics in ``pgn.repertoire`` suggest the trained side and which
headers carry chapter/title names; this dialog shows those suggestions with
their evidence, lets the user override them, and previews the resulting
chapter/title pairs so a wrong mapping is obvious before anything is created.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import chess

from chess_puzzles.pgn.repertoire import (
    DEFAULT_FIELD,
    NAMING_FIELDS,
    CourseProfile,
    ImportChoices,
)


_NO_CHAPTER_LABEL = "(none — one chapter per game)"
_AUTO_TITLE_LABEL = "(automatic)"
_PREVIEW_ROWS = 6


class RepertoireImportDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, course_name: str, profile: CourseProfile) -> None:
        super().__init__(parent, name="repertoireimport", class_="ChessPuzzlesRepertoireImport")
        self.title("Import Opening Course")
        self.transient(parent)
        self.resizable(False, False)
        self.result: ImportChoices | None = None
        self._profile = profile

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(body, text=f"{course_name} — {profile.game_count} game(s)").grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )

        side_default = "black" if profile.trained_side == chess.BLACK else "white"
        self.side_var = tk.StringVar(value=side_default)
        side_frame = ttk.Frame(body)
        side_frame.grid(row=1, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Label(side_frame, text="Train as").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Radiobutton(side_frame, text="White", value="white", variable=self.side_var).pack(
            side=tk.LEFT
        )
        ttk.Radiobutton(side_frame, text="Black", value="black", variable=self.side_var).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Label(body, text=self._side_evidence(), style="Muted.TLabel").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(0, 8)
        )

        self.chapter_var = tk.StringVar(
            value=self._field_label(profile.chapter_field, _NO_CHAPTER_LABEL)
        )
        self.title_var = tk.StringVar(
            value=self._field_label(profile.title_field, _AUTO_TITLE_LABEL)
        )
        self._build_field_row(body, 3, "Chapters from", self.chapter_var, _NO_CHAPTER_LABEL)
        self._build_field_row(body, 4, "Titles from", self.title_var, _AUTO_TITLE_LABEL)

        ttk.Label(body, text="Preview").grid(row=5, column=0, sticky="nw", pady=(8, 0))
        self.preview_var = tk.StringVar()
        ttk.Label(body, textvariable=self.preview_var, style="Muted.TLabel", justify=tk.LEFT).grid(
            row=5, column=1, sticky="w", pady=(8, 0)
        )
        self._update_preview()

        footer = ttk.Frame(body)
        footer.grid(row=6, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(footer, text="Import", command=self._accept).pack(side=tk.RIGHT, padx=(0, 6))

        body.columnconfigure(1, weight=1)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Return>", lambda _event: self._accept())
        self.bind("<Escape>", lambda _event: self.destroy())

    def show_modal(self) -> ImportChoices | None:
        self.grab_set()
        self.wait_window()
        return self.result

    def _side_evidence(self) -> str:
        white, black = self._profile.white_finishers, self._profile.black_finishers
        if not white and not black:
            return "No line evidence found in this file."
        return f"Lines ending on a White move: {white}, on a Black move: {black}."

    def _field_label(self, field: str, none_label: str) -> str:
        if field == DEFAULT_FIELD:
            return none_label
        for candidate in self._profile.fields:
            if candidate.name == field and candidate.samples:
                return f'{field} — e.g. "{_shorten(candidate.samples[0])}"'
        return field

    def _field_from_label(self, label: str) -> str:
        name = label.split(" — ")[0]
        return name if name in NAMING_FIELDS else DEFAULT_FIELD

    def _build_field_row(
        self, parent: ttk.Frame, row: int, label: str, var: tk.StringVar, none_label: str
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=(0, 8))
        values = [none_label] + [self._field_label(name, none_label) for name in NAMING_FIELDS]
        combo = ttk.Combobox(parent, textvariable=var, values=values, state="readonly", width=44)
        combo.grid(row=row, column=1, sticky="w", pady=4)
        combo.bind("<<ComboboxSelected>>", lambda _event: self._update_preview())

    def _update_preview(self) -> None:
        chapter_field = self._field_from_label(self.chapter_var.get())
        title_field = self._field_from_label(self.title_var.get())
        rows = []
        for headers in self._profile.header_samples[:_PREVIEW_ROWS]:
            chapter = _header(headers, chapter_field) or "(game title)"
            title = _header(headers, title_field) or "(automatic)"
            rows.append(f"{_shorten(chapter)}  ›  {_shorten(title)}")
        self.preview_var.set("\n".join(rows) if rows else "(no games)")

    def _accept(self) -> None:
        self.result = ImportChoices(
            trained_side=chess.WHITE if self.side_var.get() == "white" else chess.BLACK,
            chapter_field=self._field_from_label(self.chapter_var.get()),
            title_field=self._field_from_label(self.title_var.get()),
        )
        self.destroy()


def _header(headers: dict[str, str], field: str) -> str:
    if field == DEFAULT_FIELD:
        return ""
    value = headers.get(field, "").strip()
    return "" if value == "?" else value


def _shorten(text: str, limit: int = 38) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
