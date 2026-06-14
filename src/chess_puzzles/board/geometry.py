from __future__ import annotations

from dataclasses import dataclass

import chess


@dataclass(frozen=True, slots=True)
class BoardRegion:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True, slots=True)
class BoardGeometry:
    canvas_width: int
    canvas_height: int
    left: float
    top: float
    side: float

    @classmethod
    def from_canvas(cls, width: int, height: int) -> "BoardGeometry":
        side = float(max(1, min(width, height)))
        return cls(
            canvas_width=width,
            canvas_height=height,
            left=(width - side) / 2,
            top=(height - side) / 2,
            side=side,
        )

    @property
    def square_size(self) -> float:
        return self.side / 8

    def display_coords(self, square: int, flipped: bool) -> tuple[int, int]:
        file_index = chess.square_file(square)
        rank_index = chess.square_rank(square)
        if flipped:
            return 7 - file_index, rank_index
        return file_index, 7 - rank_index

    def square_from_display(self, display_file: int, display_rank: int, flipped: bool) -> int:
        if flipped:
            return chess.square(7 - display_file, display_rank)
        return chess.square(display_file, 7 - display_rank)

    def square_at_pixel(self, x: float, y: float, flipped: bool) -> int | None:
        if x < self.left or y < self.top or x >= self.left + self.side or y >= self.top + self.side:
            return None
        display_file = int((x - self.left) // self.square_size)
        display_rank = int((y - self.top) // self.square_size)
        return self.square_from_display(display_file, display_rank, flipped)

    def square_top_left(self, square: int, flipped: bool) -> tuple[float, float]:
        display_file, display_rank = self.display_coords(square, flipped)
        return (
            self.left + display_file * self.square_size,
            self.top + display_rank * self.square_size,
        )

    def square_center(self, square: int, flipped: bool) -> tuple[float, float]:
        x, y = self.square_top_left(square, flipped)
        half = self.square_size / 2
        return x + half, y + half

    def square_region(self, square: int, flipped: bool) -> BoardRegion:
        x, y = self.square_top_left(square, flipped)
        return BoardRegion(x=x, y=y, width=self.square_size, height=self.square_size)

    def square_pixel_region(self, square: int, flipped: bool) -> tuple[int, int, int, int]:
        """Integer ``(x1, y1, x2, y2)`` for a square, snapped to whole pixels.

        Each edge is the rounded cumulative grid line, so a square's right/bottom
        edge is exactly the next square's left/top edge: fills tile without seams
        and any overlay (annotations, selection, hints) lines up with them to the
        pixel. Drawing from raw ``square_top_left + square_size`` floats instead
        lets fills and overlays round apart, which misaligns the borders.
        """
        display_file, display_rank = self.display_coords(square, flipped)
        x1 = round(self.left + display_file * self.square_size)
        y1 = round(self.top + display_rank * self.square_size)
        x2 = round(self.left + (display_file + 1) * self.square_size)
        y2 = round(self.top + (display_rank + 1) * self.square_size)
        return x1, y1, x2, y2
