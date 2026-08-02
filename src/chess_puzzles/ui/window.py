"""Shared top-level window sizing."""

from __future__ import annotations

import tkinter as tk


def fit_window(window: tk.Tk | tk.Toplevel, preferred: str = "") -> None:
    """Open ``window`` at ``preferred`` size, never smaller than its content.

    Hardcoded pixel geometry clips as soon as the user picks a larger
    application font: a dialog footer stops fitting and pack simply never
    places its last button. Measuring what the widgets ask for keeps that from
    depending on the font, so ``preferred`` (``"WIDTHxHEIGHT"``, optional) only
    ever makes the window bigger, and the content size becomes the minsize so
    it cannot be dragged smaller than itself either.

    Call once, after the widgets are built.
    """
    window.update_idletasks()
    wanted_width, _, wanted_height = preferred.partition("x")
    # An enormous font must not push the window off the screen it has to fit on.
    floor_width = min(window.winfo_reqwidth(), int(window.winfo_screenwidth() * 0.9))
    floor_height = min(window.winfo_reqheight(), int(window.winfo_screenheight() * 0.9))
    window.minsize(floor_width, floor_height)
    window.geometry(f"{max(floor_width, int(wanted_width or 0))}x{max(floor_height, int(wanted_height or 0))}")
