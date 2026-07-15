"""Reusable multi-select control for Lichess puzzle themes."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterable, Sequence
from tkinter import ttk

from chess_puzzles.settings.theme_repository import UiTheme


class ThemeSelector(ttk.LabelFrame):
    """Choose zero or more values from a fixed theme vocabulary.

    Dialogs own their surrounding fields and consume ``selected`` on accept;
    this widget owns the shared add/remove/clear behavior and themed listbox.
    An empty selection deliberately means "any theme".
    """

    def __init__(
        self,
        parent: tk.Misc,
        ui_theme: UiTheme,
        choices: Sequence[str],
        *,
        title: str = "Themes",
        selected: Iterable[str] = (),
        height: int = 7,
    ) -> None:
        super().__init__(parent, text=title)
        self._choices = tuple(sorted(dict.fromkeys(choices)))
        allowed = set(self._choices)
        self._selected = list(dict.fromkeys(value for value in selected if value in allowed))
        self.choice_var = tk.StringVar(value=self._initial_choice())
        self.columnconfigure(0, weight=1)

        chooser = ttk.Frame(self)
        chooser.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        chooser.columnconfigure(0, weight=1)
        ttk.Label(chooser, text="Add theme").grid(row=0, column=0, sticky="w")
        self.combobox = ttk.Combobox(
            chooser,
            state="readonly",
            values=self._choices,
            textvariable=self.choice_var,
            width=24,
        )
        self.combobox.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(chooser, text="Add", command=self._add).grid(row=1, column=1, sticky="e")

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
            text="No themes selected means any theme.",
            style="Muted.TLabel",
        ).pack(side=tk.LEFT, padx=(12, 0))
        self._refresh()

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
