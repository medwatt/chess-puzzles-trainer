from __future__ import annotations

import tkinter as tk
from tkinter import font, ttk

from chess_puzzles.constants import FONT_DIALOG_GEOMETRY
from chess_puzzles.settings.model import AppSettings


FONT_STYLE_LABELS = {
    "Regular": "regular",
    "Bold": "bold",
    "Italic": "italic",
    "Bold Italic": "bold italic",
}


class FontChooserDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, settings: AppSettings) -> None:
        super().__init__(parent, name="fontchooser", class_="ChessPuzzlesFontChooser")
        self.title("Choose font")
        self.transient(parent)
        self.geometry(FONT_DIALOG_GEOMETRY)
        self.result: tuple[str, str, int] | None = None

        current_family = settings.font_family or font.nametofont("TkDefaultFont").actual("family")
        families = sorted(set(font.families(parent)))
        if current_family not in families:
            families.insert(0, current_family)

        self.family_var = tk.StringVar(value=current_family)
        self.style_var = tk.StringVar(value=self._style_label(settings.font_style))
        self.size_var = tk.IntVar(value=settings.font_size)

        root = ttk.Frame(self, padding=10)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)

        ttk.Label(root, text="Family").grid(row=0, column=0, sticky="w")
        frame = ttk.Frame(root)
        frame.grid(row=1, column=0, sticky="nsew", pady=(2, 8))
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.family_list = tk.Listbox(frame, exportselection=False)
        scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.family_list.yview)
        self.family_list.configure(yscrollcommand=scroll.set)
        self.family_list.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        for family_name in families:
            self.family_list.insert(tk.END, family_name)
        index = families.index(current_family)
        self.family_list.selection_set(index)
        self.family_list.see(index)
        self.family_list.bind("<<ListboxSelect>>", self._family_selected)

        controls = ttk.Frame(root)
        controls.grid(row=2, column=0, sticky="ew")
        ttk.Label(controls, text="Style").grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Combobox(controls, textvariable=self.style_var, values=list(FONT_STYLE_LABELS), state="readonly", width=14).grid(
            row=0,
            column=1,
            sticky="w",
        )
        ttk.Label(controls, text="Size").grid(row=0, column=2, sticky="w", padx=(18, 6))
        ttk.Spinbox(controls, from_=6, to=32, textvariable=self.size_var, width=6).grid(row=0, column=3, sticky="w")

        footer = ttk.Frame(root)
        footer.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        ttk.Button(footer, text="Cancel", command=self.destroy).pack(side=tk.RIGHT)
        ttk.Button(footer, text="OK", command=self._accept).pack(side=tk.RIGHT, padx=(0, 6))
        self.bind("<Return>", lambda _event: self._accept())
        self.bind("<Escape>", lambda _event: self.destroy())

    def show_modal(self) -> tuple[str, str, int] | None:
        self.grab_set()
        self.wait_window()
        return self.result

    def _family_selected(self, _event: tk.Event) -> None:
        selection = self.family_list.curselection()
        if selection:
            self.family_var.set(self.family_list.get(selection[0]))

    def _accept(self) -> None:
        self.result = (self.family_var.get(), FONT_STYLE_LABELS.get(self.style_var.get(), "regular"), int(self.size_var.get()))
        self.destroy()

    def _style_label(self, style: str) -> str:
        for label, key in FONT_STYLE_LABELS.items():
            if key == style:
                return label
        return "Regular"
