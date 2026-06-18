"""Where drill positions come from.

The default source streams the Lichess puzzle CSV: it seeks to a random byte
offset and scans forward for the next row whose FEN the drill accepts. Because
almost every real position qualifies for most drills, this finds a match within
a handful of lines -- no precomputed index needed. Tests inject the in-memory
``ListPositionSource`` instead.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import chess

from chess_puzzles.vision.filters import Accepts

# Lichess CSV columns: PuzzleId, FEN, Moves, ...
_FEN_COLUMN = 1
# How many consecutive rows to scan from a random offset before re-seeking.
_SCAN_LINES = 4000
# How many random seeks to try before giving up on a drill's filter.
_MAX_SEEKS = 64


class PositionUnavailable(RuntimeError):
    """Raised when no position satisfying the drill's filter could be found."""


class PositionSource(Protocol):
    def next(self, accepts: Accepts, rng: random.Random) -> chess.Board:
        """Return a board the drill accepts, or raise ``PositionUnavailable``."""
        ...


@dataclass(frozen=True, slots=True)
class ListPositionSource:
    """An in-memory source over a fixed list of FENs (used in tests)."""

    fens: tuple[str, ...]

    def next(self, accepts: Accepts, rng: random.Random) -> chess.Board:
        matching = [board for board in map(_board_from_fen, self.fens) if board is not None and accepts(board)]
        if not matching:
            raise PositionUnavailable("No FEN in the list satisfies the drill filter.")
        return rng.choice(matching)


class LichessCsvSource:
    """Streams random positions from a Lichess puzzle CSV file."""

    def __init__(self, csv_path: str | Path) -> None:
        self._path = Path(csv_path)
        if not self._path.is_file():
            raise PositionUnavailable(f"Lichess CSV not found: {self._path}")
        self._size = self._path.stat().st_size
        if self._size == 0:
            raise PositionUnavailable(f"Lichess CSV is empty: {self._path}")

    def next(self, accepts: Accepts, rng: random.Random) -> chess.Board:
        with self._path.open("rb") as handle:
            for _ in range(_MAX_SEEKS):
                handle.seek(rng.randrange(self._size))
                handle.readline()  # discard the partial line landed in
                for _ in range(_SCAN_LINES):
                    raw = handle.readline()
                    if not raw:
                        break  # hit EOF; re-seek
                    board = _board_from_csv_line(raw)
                    if board is not None and accepts(board):
                        return board
        raise PositionUnavailable("Scanned the CSV without finding a matching position.")


def _board_from_csv_line(raw: bytes) -> chess.Board | None:
    try:
        fields = raw.decode("utf-8").rstrip("\n").split(",")
    except UnicodeDecodeError:
        return None
    if len(fields) <= _FEN_COLUMN:
        return None
    return _board_from_fen(fields[_FEN_COLUMN])


def _board_from_fen(fen: str) -> chess.Board | None:
    try:
        return chess.Board(fen)
    except ValueError:
        return None
