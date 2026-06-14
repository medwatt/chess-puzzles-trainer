from __future__ import annotations

from collections.abc import Callable
import tkinter as tk

from chess_puzzles.settings.theme_repository import UiTheme


TOOLTIP_DELAY_MS = 450


class ThemedTooltip:
    def __init__(self, widget: tk.Widget, text: str, theme_getter: Callable[[], UiTheme]) -> None:
        self.widget = widget
        self.text = text
        self.theme_getter = theme_getter
        self._after_id: str | None = None
        self._window: tk.Toplevel | None = None
        self._label: tk.Label | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")
        widget.bind("<FocusOut>", self._hide, add="+")

    def _schedule(self, _event: tk.Event | None = None) -> None:
        self._cancel()
        self._after_id = self.widget.after(TOOLTIP_DELAY_MS, self._show)

    def _cancel(self) -> None:
        if self._after_id is not None:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

    def _show(self) -> None:
        self._after_id = None
        if self._window is not None or not self.text:
            return
        if not self.widget.winfo_viewable():
            return
        self._window = tk.Toplevel(self.widget)
        self._window.wm_overrideredirect(True)
        self._label = tk.Label(
            self._window,
            text=self.text,
            justify=tk.LEFT,
            relief=tk.SOLID,
            borderwidth=1,
            padx=8,
            pady=4,
            font="TkDefaultFont",
        )
        self._label.pack()
        self.apply_theme()
        x = self.widget.winfo_rootx() + 8
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self._window.wm_geometry(f"+{x}+{y}")

    def _hide(self, _event: tk.Event | None = None) -> None:
        self._cancel()
        if self._window is not None:
            self._window.destroy()
            self._window = None
            self._label = None

    def apply_theme(self) -> None:
        if self._window is None or self._label is None:
            return
        theme = self.theme_getter()
        self._window.configure(bg=theme.border)
        self._label.configure(
            background=theme.field_bg,
            foreground=theme.field_text,
            highlightbackground=theme.border,
            activebackground=theme.field_bg,
            activeforeground=theme.field_text,
        )
