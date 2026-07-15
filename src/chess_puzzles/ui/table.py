"""Shared ttk.Treeview helpers."""

from __future__ import annotations

import heapq
from tkinter import font as tkfont
from tkinter import ttk

# Character count tracks rendered width closely enough that the widest string
# is practically always among the few longest ones; measuring only those keeps
# the cost independent of table size (the course editor holds thousands of
# rows, and a font.measure per cell was observed to take minutes).
_MEASURE_CANDIDATES = 8


def autosize_columns(tree: ttk.Treeview, *, padding: int = 28, max_width: int = 520) -> None:
    """Fit each column of a headings-style Treeview to its content.

    Hardcoded pixel widths truncate as soon as the user configures a larger
    application font; measuring the rendered strings with the fonts actually
    in effect keeps every table readable at any font size.

    Call after populating (or repopulating) the table. Columns keep whatever
    ``anchor``/``stretch`` the caller configured. ``max_width`` stops one
    long value (a file path, a course name) from blowing up the whole
    dialog -- stretch columns can still grow past it when space allows.
    """
    body_font = tkfont.nametofont("TkDefaultFont")
    heading_font = tkfont.nametofont("TkHeadingFont")
    columns = list(tree["columns"])
    values_by_column: list[list[str]] = [[] for _ in columns]
    for row in tree.get_children():
        for index, value in enumerate(tree.item(row, "values")[: len(columns)]):
            values_by_column[index].append(str(value))
    for index, column in enumerate(columns):
        width = heading_font.measure(tree.heading(column)["text"])
        candidates = heapq.nlargest(_MEASURE_CANDIDATES, set(values_by_column[index]), key=len)
        for text in candidates:
            width = max(width, body_font.measure(text))
        tree.column(column, width=min(width + padding, max_width))
