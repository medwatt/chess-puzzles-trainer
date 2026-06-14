"""The per-drill options panel.

Renders a drill's declared ``OPTIONS`` generically and reads them back into a
configured drill via ``dataclasses.replace``. Extracted from the window so the
reflective widget-building lives behind a small API, and so its fiddly value
mapping (the ``resolve_option_value`` / ``initial_label`` helpers) is pure and
unit-testable without a Tk display.
"""

from __future__ import annotations

import dataclasses
import tkinter as tk
from tkinter import ttk

from chess_puzzles.vision.drill import Drill, DrillOption, drill_options


def resolve_option_value(option: DrillOption, raw: object) -> object:
    """Turn a widget's raw value into the drill field value it stands for.

    A boolean option (``choices is None``) maps the checkbox state; a choice
    option maps the selected label back to its paired value.
    """
    if option.choices is None:
        return bool(raw)
    return {label: value for label, value in option.choices}[raw]


def initial_label(option: DrillOption, current: object) -> str:
    """The dropdown label whose value matches the drill's current field value."""
    choices = option.choices
    assert choices is not None  # only meaningful for choice options
    return next((label for label, value in choices if value == current), choices[0][0])


class OptionsPanel(ttk.LabelFrame):
    """A labelled frame that mirrors the selected drill's options as widgets."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, text="Options", padding=(8, 6))
        self.columnconfigure(1, weight=1)
        self._controls: list[tuple[str, tk.Variable, DrillOption]] = []
        self._widgets: list[tk.Widget] = []

    def show(self, drill: Drill) -> None:
        """Rebuild the controls to match ``drill``'s declared options."""
        for child in self.winfo_children():
            child.destroy()
        self._controls = []
        self._widgets = []
        options = drill_options(drill)
        if not options:
            ttk.Label(self, text="No options for this drill.").grid(row=0, column=0, columnspan=2, sticky="w")
            return
        for row, option in enumerate(options):
            current = getattr(drill, option.key)
            if option.choices is None:
                var: tk.Variable = tk.BooleanVar(value=bool(current))
                widget: tk.Widget = ttk.Checkbutton(self, text=option.label, variable=var, takefocus=False)
                widget.grid(row=row, column=0, columnspan=2, sticky="w", pady=1)
            else:
                ttk.Label(self, text=option.label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=1)
                var = tk.StringVar(value=initial_label(option, current))
                widget = ttk.Combobox(
                    self,
                    values=[label for label, _ in option.choices],
                    textvariable=var,
                    state="readonly",
                    takefocus=False,
                )
                widget.grid(row=row, column=1, sticky="ew", pady=1)
            self._controls.append((option.key, var, option))
            self._widgets.append(widget)

    def configured(self, drill: Drill) -> Drill:
        """Return ``drill`` with its option fields set from the current widgets."""
        if not self._controls:
            return drill
        values = {key: resolve_option_value(option, var.get()) for key, var, option in self._controls}
        return dataclasses.replace(drill, **values)

    def set_enabled(self, enabled: bool) -> None:
        for widget in self._widgets:
            if isinstance(widget, ttk.Combobox):
                widget.configure(state="readonly" if enabled else "disabled")
            else:
                widget.configure(state="normal" if enabled else "disabled")
