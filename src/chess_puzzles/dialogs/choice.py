from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class ChoiceDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, title: str, label: str, choices: list[str], default: str | None = None) -> None:
        super().__init__(parent, name="choicedialog", class_="ChessPuzzlesChoiceDialog")
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        self.result: str | None = None

        ttk.Label(self, text=label).pack(fill=tk.X, padx=12, pady=(12, 4))
        initial_value = default if default in choices else (choices[0] if choices else "")
        self.value = tk.StringVar(value=initial_value)
        width = min(72, max(24, *(len(choice) for choice in choices))) if choices else 24
        self.combo = ttk.Combobox(self, textvariable=self.value, values=choices, state="readonly", width=width)
        self.combo.pack(fill=tk.X, padx=12, pady=4)
        self.combo.focus_set()

        footer = ttk.Frame(self)
        footer.pack(fill=tk.X, padx=12, pady=(8, 12))
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(footer, text="OK", command=self._accept).pack(side=tk.RIGHT, padx=(0, 6))
        self.bind("<Return>", lambda _event: self._accept())
        self.bind("<Escape>", lambda _event: self.destroy())

    def show_modal(self) -> str | None:
        self.grab_set()
        self.wait_window()
        return self.result

    def _accept(self) -> None:
        self.result = self.value.get()
        self.destroy()
