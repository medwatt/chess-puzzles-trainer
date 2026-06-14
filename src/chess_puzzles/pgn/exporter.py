from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from chess_puzzles.pgn.utils import pgn_for_puzzle
from chess_puzzles.puzzle import Puzzle


def export_puzzles_to_pgn(puzzles: Iterable[Puzzle], path: str | Path) -> int:
    """Write puzzles (one game each, blank-line separated) to a .pgn and return the count.

    The file is written atomically (temp file + os.replace).
    """
    path = Path(path)
    tmp_path = path.with_name(path.name + ".tmp")
    count = 0
    with tmp_path.open("w", encoding="utf-8") as handle:
        for puzzle in puzzles:
            if count:
                handle.write("\n")
            handle.write(pgn_for_puzzle(puzzle).rstrip("\n") + "\n")
            count += 1
    os.replace(tmp_path, path)
    return count
