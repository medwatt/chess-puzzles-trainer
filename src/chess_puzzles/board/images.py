from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from pathlib import Path

import chess


PIECE_SHEET_ORDER = {
    (chess.WHITE, chess.PAWN): 0,
    (chess.WHITE, chess.KNIGHT): 1,
    (chess.WHITE, chess.BISHOP): 2,
    (chess.WHITE, chess.ROOK): 3,
    (chess.WHITE, chess.QUEEN): 4,
    (chess.WHITE, chess.KING): 5,
    (chess.BLACK, chess.PAWN): 6,
    (chess.BLACK, chess.KNIGHT): 7,
    (chess.BLACK, chess.BISHOP): 8,
    (chess.BLACK, chess.ROOK): 9,
    (chess.BLACK, chess.QUEEN): 10,
    (chess.BLACK, chess.KING): 11,
}


@dataclass(slots=True)
class PieceImageCache:
    _sheet_cache: dict[Path, tk.PhotoImage]
    _piece_cache: dict[tuple[Path, int, int], tk.PhotoImage]
    _best_sheet_cache: dict[tuple[Path, int], tuple[Path | None, int]]

    def __init__(self) -> None:
        self._sheet_cache = {}
        self._piece_cache = {}
        self._best_sheet_cache = {}

    def clear(self) -> None:
        self._sheet_cache.clear()
        self._piece_cache.clear()
        self._best_sheet_cache.clear()

    def image_for(self, piece: chess.Piece, directory: Path, requested_size: int) -> tk.PhotoImage | None:
        sheet_path, tile_size = self._best_sheet(directory, requested_size)
        if sheet_path is None:
            return None

        column = PIECE_SHEET_ORDER[(piece.color, piece.piece_type)]
        key = (sheet_path, tile_size, column)
        if key in self._piece_cache:
            return self._piece_cache[key]

        sheet = self._sheet_cache.get(sheet_path)
        if sheet is None:
            sheet = tk.PhotoImage(file=str(sheet_path))
            self._sheet_cache[sheet_path] = sheet

        x0 = column * tile_size
        cropped = tk.PhotoImage(width=tile_size, height=tile_size)
        cropped.tk.call(
            cropped.name, "copy", sheet.name,
            "-from", x0, 0, x0 + tile_size, tile_size,
            "-to", 0, 0, tile_size, tile_size,
        )
        self._piece_cache[key] = cropped
        return cropped

    def _best_sheet(self, directory: Path, requested_size: int) -> tuple[Path | None, int]:
        key = (directory, requested_size)
        if key in self._best_sheet_cache:
            return self._best_sheet_cache[key]

        candidates: list[tuple[int, Path]] = []
        for path in directory.iterdir() if directory.exists() else ():
            if path.suffix.lower() not in {".png", ".gif"}:
                continue
            try:
                size = int(path.stem.rsplit("_", 1)[1])
            except (IndexError, ValueError):
                continue
            candidates.append((size, path))

        if not candidates:
            result = (None, 0)
        else:
            fitting = [(size, path) for size, path in candidates if size <= requested_size]
            size, path = max(fitting, key=lambda item: item[0]) if fitting else min(candidates, key=lambda item: item[0])
            result = (path, size)
        self._best_sheet_cache[key] = result
        return result


class BoardTextureCache:
    def __init__(self) -> None:
        self._source_cache: dict[Path, tk.PhotoImage] = {}
        self._square_cache: dict[tuple[Path, int], tk.PhotoImage] = {}

    def clear(self) -> None:
        self._source_cache.clear()
        self._square_cache.clear()

    def image_for(self, path: Path, square_size: int) -> tk.PhotoImage | None:
        if not path.exists():
            return None

        key = (path, square_size)
        if key in self._square_cache:
            return self._square_cache[key]

        source = self._source_cache.get(path)
        if source is None:
            source = tk.PhotoImage(file=str(path))
            self._source_cache[path] = source

        image = tk.PhotoImage(width=square_size, height=square_size)
        image.tk.call(
            image.name, "copy", source.name,
            "-to", 0, 0, square_size, square_size,
            "-compositingrule", "set",
        )
        self._square_cache[key] = image
        return image
