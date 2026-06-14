from __future__ import annotations

from pathlib import Path

from chess_puzzles.board.images import PieceImageCache


def test_piece_image_cache_returns_path_then_tile_size(tmp_path: Path) -> None:
    sheet = tmp_path / "cburnett_75.png"
    sheet.write_bytes(b"not used by this test")

    cache = PieceImageCache()

    assert cache._best_sheet(tmp_path, 80) == (sheet, 75)
