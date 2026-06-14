from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable

from chess_puzzles.board import BoardCapabilities, BoardView
from chess_puzzles.board.input import BoardEvent, BoardFlipped
from chess_puzzles.engine.evaluation_bar import EVALUATION_BAR_GAP, EVALUATION_BAR_WIDTH, EvaluationBar


EventHandler = Callable[[BoardEvent], None]


class BoardAnalysisFrame(ttk.Frame):
    """Frame combining an evaluation bar and a square board canvas."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        capabilities: BoardCapabilities | None = None,
        event_handler: EventHandler | None = None,
        evaluation_bar_visible: bool = False,
    ) -> None:
        super().__init__(master)
        self._evaluation_bar_visible = evaluation_bar_visible
        self.evaluation_bar = EvaluationBar(self)
        self.board = BoardView(self, capabilities=capabilities, event_handler=self._dispatch_event)
        self._user_handler = event_handler
        self.bind("<Configure>", lambda _event: self._layout_children())

    def set_evaluation_bar_visible(self, visible: bool) -> None:
        if self._evaluation_bar_visible == visible:
            return
        self._evaluation_bar_visible = visible
        self._layout_children()

    def _dispatch_event(self, event: BoardEvent) -> None:
        if isinstance(event, BoardFlipped):
            self.evaluation_bar.set_flipped(event.flipped)
        if self._user_handler is not None:
            self._user_handler(event)

    def _layout_children(self) -> None:
        width = self.winfo_width()
        height = self.winfo_height()
        bar_space = EVALUATION_BAR_WIDTH + EVALUATION_BAR_GAP if self._evaluation_bar_visible else 0
        board_side = max(1, min(height, max(1, width - bar_space)))
        group_width = bar_space + board_side
        group_x = max(0.0, (width - group_width) / 2)
        board_x = group_x + bar_space
        board_y = max(0.0, (height - board_side) / 2)

        self.board.place(x=board_x, y=board_y, width=board_side, height=board_side)
        if self._evaluation_bar_visible:
            self.evaluation_bar.place(x=group_x, y=board_y, width=EVALUATION_BAR_WIDTH, height=board_side)
        else:
            self.evaluation_bar.place_forget()
