from __future__ import annotations

import tkinter as tk

from chess_puzzles.constants import (
    EVALUATION_BAR_GAP,
    EVALUATION_BAR_LABEL_BAND_HEIGHT,
    EVALUATION_BAR_LABEL_FONT_SIZE,
    EVALUATION_BAR_WIDTH,
)
from chess_puzzles.engine.evaluation import EngineScore, bar_white_fraction


__all__ = ["EVALUATION_BAR_GAP", "EVALUATION_BAR_WIDTH", "EvaluationBar"]


# The bar represents the white/black score split, so its colors are fixed
# chess-side colors by design, not UI-theme colors.
WHITE_SIDE_FILL = "#f4f4f4"
BLACK_SIDE_FILL = "#2b2b2b"
BORDER_COLOR = "#777777"
LABEL_BAND_FILL = "#dddddd"
LABEL_TEXT_COLOR = "#111111"


class EvaluationBar(tk.Canvas):
    """Vertical white/black evaluation bar displayed beside a board."""

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, width=EVALUATION_BAR_WIDTH, height=320, highlightthickness=0, bd=0, bg=BLACK_SIDE_FILL)
        self.score: EngineScore | None = None
        self.message = ""
        self.flipped = False
        self.bind("<Configure>", lambda _event: self.redraw())

    def set_score(self, score: EngineScore | None, message: str = "") -> None:
        self.score = score
        self.message = message
        self.redraw()

    def set_flipped(self, flipped: bool) -> None:
        self.flipped = flipped
        self.redraw()

    def clear(self, message: str = "") -> None:
        self.score = None
        self.message = message
        self.redraw()

    def redraw(self) -> None:
        self.delete("all")
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        fraction = bar_white_fraction(self.score)
        white_height = int(height * fraction)
        split_y = height - white_height

        if self.flipped:
            self.create_rectangle(0, 0, width, white_height, fill=WHITE_SIDE_FILL, outline="")
            self.create_rectangle(0, white_height, width, height, fill=BLACK_SIDE_FILL, outline="")
        else:
            self.create_rectangle(0, 0, width, split_y, fill=BLACK_SIDE_FILL, outline="")
            self.create_rectangle(0, split_y, width, height, fill=WHITE_SIDE_FILL, outline="")
        # Flush border on all four edges (inset top/left looks like a floating
        # frame, and the dark side blends into dark UI themes without it).
        self.create_rectangle(0, 0, width - 1, height - 1, outline=BORDER_COLOR)

        label = self.message or (self.score.label if self.score is not None else "")
        if not label:
            return
        font = ("TkDefaultFont", EVALUATION_BAR_LABEL_FONT_SIZE, "bold")
        cx = width / 2
        half = EVALUATION_BAR_LABEL_BAND_HEIGHT / 2
        boundary = white_height if self.flipped else split_y
        cy = max(half, min(height - half, boundary))
        self.create_rectangle(0, cy - half, width, cy + half, fill=LABEL_BAND_FILL, outline="")
        self.create_text(cx, cy, text=label, fill=LABEL_TEXT_COLOR, font=font)
