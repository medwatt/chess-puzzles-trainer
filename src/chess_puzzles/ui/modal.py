"""Shared modal-dialog plumbing."""

from __future__ import annotations

import tkinter as tk


# A transient dialog's parent must be a real window: Tk.wm_transient reparents
# to a window manager entry, so any other widget is a runtime error, not just a
# loose annotation.
ModalParent = tk.Tk | tk.Toplevel


def run_modal(window: tk.Toplevel) -> None:
    """Grab input for ``window`` and block until it is destroyed.

    ``grab_set`` fails on a window the window manager has not mapped yet, so
    the visibility wait is what keeps the grab from racing - the stdlib's own
    ``tkinter.simpledialog.Dialog`` opens the same way. Losing that race raised
    straight out of the caller, leaving the dialog on screen looking normal
    while the code meant to read its result was already gone.
    """
    window.wait_visibility()
    window.grab_set()
    window.wait_window()
