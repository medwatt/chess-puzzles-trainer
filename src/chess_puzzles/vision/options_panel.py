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
from collections.abc import Callable, Mapping
from enum import Enum
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


def _serialize(value: object) -> object:
    """A drill field value's JSON-native form (an enum becomes its ``.value``)."""
    return value.value if isinstance(value, Enum) else value


def storage_value(option: DrillOption, raw: object) -> object:
    """The JSON-native value to persist for a widget's current raw value.

    Stores the underlying field value (an enum's code, a float, a bool) rather than
    the display label, so renaming a label never orphans a saved preference.
    """
    return _serialize(resolve_option_value(option, raw))


def stored_label(option: DrillOption, stored: object, current: object) -> str:
    """The dropdown label whose underlying value serializes to ``stored``.

    Falls back to the drill's current value when ``stored`` matches no choice (an
    option whose values changed, or absent from the saved file)."""
    choices = option.choices
    assert choices is not None  # only meaningful for choice options
    return next((label for label, value in choices if _serialize(value) == stored), initial_label(option, current))


class OptionsPanel(ttk.LabelFrame):
    """A labelled frame that mirrors the selected drill's options as widgets."""

    def __init__(self, parent: tk.Misc, on_change: Callable[[], None] | None = None) -> None:
        super().__init__(parent, text="Options", padding=(8, 6))
        self.columnconfigure(1, weight=1)
        self._on_change = on_change
        self._controls: list[tuple[str, tk.Variable, DrillOption]] = []
        self._widgets: list[tk.Widget] = []

    def show(self, drill: Drill, saved: Mapping[str, object] | None = None) -> None:
        """Rebuild the controls to match ``drill``'s declared options.

        ``saved`` supplies stored JSON-native option values (keyed by option key); an
        entry that no longer fits its option is ignored, falling back to the
        drill's current field value.
        """
        saved = saved or {}
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
            remembered = saved.get(option.key)
            if option.choices is None:
                value = bool(remembered) if isinstance(remembered, bool) else bool(current)
                var: tk.Variable = tk.BooleanVar(value=value)
                widget: tk.Widget = ttk.Checkbutton(
                    self, text=option.label, variable=var, command=self._notify, takefocus=False
                )
                widget.grid(row=row, column=0, columnspan=2, sticky="w", pady=1)
            else:
                ttk.Label(self, text=option.label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=1)
                labels = [label for label, _ in option.choices]
                var = tk.StringVar(value=stored_label(option, remembered, current))
                widget = ttk.Combobox(
                    self, values=labels, textvariable=var, state="readonly", takefocus=False
                )
                widget.bind("<<ComboboxSelected>>", lambda _event: self._notify())
                widget.grid(row=row, column=1, sticky="ew", pady=1)
            self._controls.append((option.key, var, option))
            self._widgets.append(widget)

    def raw_values(self) -> dict[str, object]:
        """The current options as JSON-native underlying values, keyed by option key.

        This is exactly what gets persisted; ``show(drill, saved)`` consumes it back.
        """
        return {key: storage_value(option, var.get()) for key, var, option in self._controls}

    def _notify(self) -> None:
        if self._on_change is not None:
            self._on_change()

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
