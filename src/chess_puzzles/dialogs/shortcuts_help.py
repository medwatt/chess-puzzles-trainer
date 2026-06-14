from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from chess_puzzles.settings.theme_repository import UiTheme
from chess_puzzles.shortcuts import MENU_ACCELERATORS, SHORTCUT_HELP_SECTIONS


class ShortcutsHelpDialog(tk.Toplevel):
    """Read-only cheat sheet of the main window's keyboard shortcuts."""

    def __init__(self, parent: tk.Misc, theme: UiTheme) -> None:
        super().__init__(parent, name="shortcutshelp", class_="ChessPuzzlesShortcutsHelp")
        self.title("Keyboard Shortcuts")
        self.transient(parent)
        self.configure(bg=theme.window_bg)

        section_font = tkfont.Font(font="TkDefaultFont")
        section_font.configure(weight="bold")

        body = ttk.Frame(self, padding=8)
        body.pack(fill=tk.BOTH, expand=True)
        body.rowconfigure(0, weight=1)
        body.columnconfigure(0, weight=1)

        text = tk.Text(
            body,
            width=54,
            height=30,
            wrap=tk.NONE,
            relief=tk.FLAT,
            padx=12,
            pady=10,
            tabs=(300,),
            background=theme.field_bg,
            foreground=theme.field_text,
            highlightthickness=0,
        )
        text.tag_configure("section", font=section_font, foreground=theme.accent, spacing3=4)
        text.tag_configure("key", foreground=theme.muted_text)
        for section, entries in SHORTCUT_HELP_SECTIONS:
            text.insert(tk.END, f"{section}\n", "section")
            for label, sequence in entries:
                key = MENU_ACCELERATORS.get(sequence, sequence)
                text.insert(tk.END, f"  {label}\t")
                text.insert(tk.END, f"{key}\n", "key")
            text.insert(tk.END, "\n")
        text.configure(state=tk.DISABLED)

        scroll = ttk.Scrollbar(body, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        ttk.Button(body, text="Close", command=self.destroy, takefocus=False).grid(
            row=1, column=0, columnspan=2, pady=(8, 0)
        )
        self.bind("<Escape>", lambda _event: self.destroy())
