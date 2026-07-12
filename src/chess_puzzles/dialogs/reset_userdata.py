"""Choose which user data to delete for a fresh start on a deck.

The user store keeps several independent kinds of history; this dialog lets
each be wiped separately, with live counts so the cost of the click is
visible. Deck content is never touched -- only the user's own records.
Adding a new deletable scope means one more checkbox row here plus its
delete method on ``UserStore``.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk


@dataclass(frozen=True, slots=True)
class ResetChoices:
    attempts: bool
    favorites: bool
    position: bool
    vision: bool

    @property
    def any(self) -> bool:
        return self.attempts or self.favorites or self.position or self.vision


class ResetUserdataDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        deck_name: str,
        *,
        attempt_count: int,
        favorite_count: int,
        vision_count: int,
    ) -> None:
        super().__init__(parent, name="resetuserdata", class_="ChessPuzzlesResetUserdata")
        self.title("Reset User Data")
        self.transient(parent)
        self.resizable(False, False)
        self.result: ResetChoices | None = None

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(body, text=f"Delete recorded progress for “{deck_name}”:").grid(
            row=0, column=0, sticky="w", pady=(0, 8)
        )

        self.attempts_var = tk.BooleanVar(value=True)
        self.position_var = tk.BooleanVar(value=True)
        self.favorites_var = tk.BooleanVar(value=False)
        self.vision_var = tk.BooleanVar(value=False)
        rows = (
            (self.attempts_var, f"Solve history — {attempt_count} attempt(s)"),
            (self.position_var, "Remembered position (resume point)"),
            (self.favorites_var, f"Favorites — {favorite_count} in this deck"),
            (self.vision_var, f"Board vision history — {vision_count} drill(s), all decks"),
        )
        for index, (variable, label) in enumerate(rows, start=1):
            ttk.Checkbutton(body, text=label, variable=variable).grid(
                row=index, column=0, sticky="w", pady=2
            )

        ttk.Label(
            body, text="This cannot be undone. Deck content is not affected.", style="Muted.TLabel"
        ).grid(row=5, column=0, sticky="w", pady=(8, 0))

        footer = ttk.Frame(body)
        footer.grid(row=6, column=0, sticky="e", pady=(12, 0))
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(footer, text="Delete selected", command=self._accept).pack(
            side=tk.RIGHT, padx=(0, 6)
        )

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Return>", lambda _event: self._accept())
        self.bind("<Escape>", lambda _event: self.destroy())

    def show_modal(self) -> ResetChoices | None:
        self.grab_set()
        self.wait_window()
        return self.result

    def _accept(self) -> None:
        choices = ResetChoices(
            attempts=bool(self.attempts_var.get()),
            favorites=bool(self.favorites_var.get()),
            position=bool(self.position_var.get()),
            vision=bool(self.vision_var.get()),
        )
        self.result = choices if choices.any else None
        self.destroy()
