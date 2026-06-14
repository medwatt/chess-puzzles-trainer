from __future__ import annotations

import tkinter as tk

from chess_puzzles.board.board_view import BoardView


class BoardShortcuts:
    """Shared keyboard shortcuts for windows that host a board canvas."""

    def __init__(self, widget: tk.Misc, board: BoardView) -> None:
        self.widget = widget
        self.board = board

    def bind(self) -> None:
        self.widget.bind("<Escape>", self._clear_annotations)

    def _clear_annotations(self, _event: tk.Event) -> str:
        self.board.clear_annotations()
        return "break"
