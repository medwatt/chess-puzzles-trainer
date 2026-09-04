"""Reusable multi-select control for a fixed Lichess vocabulary."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterable, Sequence
from tkinter import ttk

from chess_puzzles.settings.theme_repository import UiTheme


class ThemeSelector(ttk.LabelFrame):
    """Choose zero or more values from a fixed theme vocabulary.

    Dialogs own their surrounding fields and consume ``selected`` on accept;
    this widget owns the shared add/remove/clear behavior and themed listbox.
    An empty selection deliberately means "any value".

    ``noun`` names what is being chosen, for the title and the hint. The search
    box narrows the dropdown as you type: the opening vocabulary is ~1,600
    entries, which is unusable as a plain scrolling list.
    """

    def __init__(
        self,
        parent: tk.Misc,
        ui_theme: UiTheme,
        choices: Sequence[str],
        *,
        title: str = "Themes",
        noun: str = "theme",
        selected: Iterable[str] = (),
        height: int = 7,
    ) -> None:
        super().__init__(parent, text=title)
        self._noun = noun
        self._choices = tuple(sorted(dict.fromkeys(choices)))
        allowed = set(self._choices)
        self._selected = list(dict.fromkeys(value for value in selected if value in allowed))
        self.choice_var = tk.StringVar(value=self._initial_choice())
        self.columnconfigure(0, weight=1)

        chooser = ttk.Frame(self)
        chooser.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        chooser.columnconfigure(0, weight=1)
        ttk.Label(chooser, text=f"Add {noun}").grid(
            row=0, column=0, columnspan=2, sticky="w"
        )
        # Full width: opening names run to "Sicilian_Defense_Najdorf_Variation".
        self.search_var = tk.StringVar()
        self.search = ttk.Entry(chooser, textvariable=self.search_var)
        self.search.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(2, 4))
        self.search_var.trace_add("write", lambda *_args: self._apply_search())
        self.combobox = ttk.Combobox(
            chooser,
            state="readonly",
            values=self._choices,
            textvariable=self.choice_var,
            width=24,
        )
        self.combobox.grid(row=2, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(chooser, text="Add", command=self._add).grid(row=2, column=1, sticky="e")

        list_frame = ttk.Frame(self)
        list_frame.grid(row=1, column=0, sticky="ew", padx=8, pady=(4, 4))
        list_frame.columnconfigure(0, weight=1)
        self.listbox = tk.Listbox(
            list_frame,
            height=height,
            selectmode=tk.EXTENDED,
            background=ui_theme.field_bg,
            foreground=ui_theme.field_text,
            selectbackground=ui_theme.menu_active_bg,
            selectforeground=ui_theme.menu_active_text,
            highlightbackground=ui_theme.border,
            highlightcolor=ui_theme.accent,
            relief=tk.FLAT,
            borderwidth=1,
        )
        self.listbox.grid(row=0, column=0, sticky="ew")
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.listbox.configure(yscrollcommand=scroll.set)

        actions = ttk.Frame(self)
        actions.grid(row=2, column=0, sticky="w", padx=8, pady=(0, 8))
        ttk.Button(actions, text="Remove selected", command=self._remove_selected).pack(
            side=tk.LEFT
        )
        ttk.Button(actions, text="Clear", command=self._clear).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(
            actions,
            text=f"No {noun} selected means any {noun}.",
            style="Muted.TLabel",
        ).pack(side=tk.LEFT, padx=(12, 0))
        self._refresh()

    def _apply_search(self) -> None:
        query = self.search_var.get().strip().casefold()
        matches = [c for c in self._choices if query in c.casefold()] if query else list(self._choices)
        self.combobox.configure(values=matches)
        # Point the box at the first match so Add works straight after typing.
        if matches and self.choice_var.get() not in matches:
            self.choice_var.set(matches[0])

    @property
    def selected(self) -> tuple[str, ...]:
        return tuple(self._selected)

    def _initial_choice(self) -> str:
        return self._selected[0] if self._selected else (self._choices[0] if self._choices else "")

    def _add(self) -> None:
        value = self.choice_var.get().strip()
        if value in self._choices and value not in self._selected:
            self._selected.append(value)
            self._refresh()

    def _remove_selected(self) -> None:
        for index in reversed(self.listbox.curselection()):
            del self._selected[index]
        self._refresh()

    def _clear(self) -> None:
        self._selected.clear()
        self._refresh()

    def _refresh(self) -> None:
        self.listbox.delete(0, tk.END)
        for value in self._selected:
            self.listbox.insert(tk.END, value)
