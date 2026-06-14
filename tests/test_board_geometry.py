from __future__ import annotations

import chess

from chess_puzzles.board.geometry import BoardGeometry


def test_square_mapping_unflipped() -> None:
    geometry = BoardGeometry.from_canvas(800, 640)

    assert geometry.square_at_pixel(80, 0, flipped=False) == chess.A8
    assert geometry.square_at_pixel(719, 639, flipped=False) == chess.H1
    assert geometry.square_top_left(chess.A1, flipped=False) == (80.0, 560.0)


def test_square_mapping_flipped() -> None:
    geometry = BoardGeometry.from_canvas(640, 640)

    assert geometry.square_at_pixel(0, 0, flipped=True) == chess.H1
    assert geometry.square_at_pixel(639, 639, flipped=True) == chess.A8
    assert geometry.square_top_left(chess.A1, flipped=True) == (560.0, 0.0)


def test_pixel_regions_are_integer_and_seamless() -> None:
    # A deliberately fractional square size (519 / 8 = 64.875).
    geometry = BoardGeometry.from_canvas(519, 519)
    for square in chess.SQUARES:
        region = geometry.square_pixel_region(square, flipped=False)
        assert all(isinstance(v, int) for v in region)

    # Horizontally and vertically adjacent squares share an exact edge -- no gaps
    # or overlaps, so fills tile and overlays line up with them.
    for rank in range(8):
        for file in range(7):
            left = geometry.square_pixel_region(chess.square(file, rank), flipped=False)
            right = geometry.square_pixel_region(chess.square(file + 1, rank), flipped=False)
            assert left[2] == right[0]  # right edge of one == left edge of next
    for file in range(8):
        for rank in range(7):
            lower = geometry.square_pixel_region(chess.square(file, rank), flipped=False)
            upper = geometry.square_pixel_region(chess.square(file, rank + 1), flipped=False)
            assert upper[3] == lower[1]  # rank+1 is drawn above rank, sharing an edge
