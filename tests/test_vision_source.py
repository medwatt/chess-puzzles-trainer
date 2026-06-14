from __future__ import annotations

import random
from pathlib import Path

import chess
import pytest

from chess_puzzles.vision.source import (
    LichessCsvSource,
    ListPositionSource,
    PositionUnavailable,
)

_HEADER = "PuzzleId,FEN,Moves,Rating,RatingDeviation,Popularity,NbPlays,Themes,GameUrl,OpeningTags\n"
_KNIGHT_FEN = "4k3/8/8/8/3N4/8/8/4K3 w - - 0 1"
_QUIET_FEN = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"


def _write_csv(path: Path, fens: list[str]) -> None:
    lines = [_HEADER]
    for i, fen in enumerate(fens):
        lines.append(f"id{i},{fen},e2e4,1500,80,90,100,theme,https://x,opening\n")
    path.write_text("".join(lines), encoding="utf-8")


def test_list_source_filters_by_accepts() -> None:
    source = ListPositionSource((_QUIET_FEN, _KNIGHT_FEN))
    board = source.next(lambda b: bool(b.pieces(chess.KNIGHT, chess.WHITE)), random.Random(0))
    assert board.pieces(chess.KNIGHT, chess.WHITE)


def test_list_source_raises_when_no_match() -> None:
    source = ListPositionSource((_QUIET_FEN,))
    with pytest.raises(PositionUnavailable):
        source.next(lambda b: bool(b.pieces(chess.KNIGHT, chess.WHITE)), random.Random(0))


def test_csv_source_returns_valid_board(tmp_path: Path) -> None:
    csv_path = tmp_path / "puzzles.csv"
    _write_csv(csv_path, [_QUIET_FEN] * 20 + [_KNIGHT_FEN] * 20)
    source = LichessCsvSource(csv_path)
    board = source.next(lambda b: bool(b.pieces(chess.KNIGHT, chess.WHITE)), random.Random(1))
    assert board.pieces(chess.KNIGHT, chess.WHITE)


def test_csv_source_missing_file(tmp_path: Path) -> None:
    with pytest.raises(PositionUnavailable):
        LichessCsvSource(tmp_path / "nope.csv")
