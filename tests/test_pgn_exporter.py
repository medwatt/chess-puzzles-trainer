from __future__ import annotations

from io import StringIO
from pathlib import Path

from chess_puzzles.pgn import PgnLoader
from chess_puzzles.pgn.exporter import export_puzzles_to_pgn
from chess_puzzles.store import ContentDatabase, ContentMeta


PGN = """
[Event "Training"]
[White "Alpha"]
[Black "Beta"]

1. e4 {first} e5 {reply} 2. Nf3 *
"""


def test_export_round_trips_moves_and_comments(tmp_path: Path) -> None:
    puzzles = PgnLoader().load(StringIO(PGN))
    out = tmp_path / "out.pgn"
    assert export_puzzles_to_pgn(puzzles, out) == 1

    reloaded = PgnLoader().load_file(out)
    assert len(reloaded) == 1
    assert reloaded[0].moves == puzzles[0].moves
    assert reloaded[0].comments[1] == "first"


def test_pgn_round_trip_through_content_database(tmp_path: Path) -> None:
    puzzles = PgnLoader().load(StringIO(PGN))
    meta = ContentMeta(database_id="d", name="N", created_at="t", updated_at="t")
    first = ContentDatabase.create(tmp_path / "a.cpdb", meta, puzzles)

    out = tmp_path / "round.pgn"
    export_puzzles_to_pgn(first.iter_puzzles(), out)

    second = ContentDatabase.create(tmp_path / "b.cpdb", meta, PgnLoader().load_file(out))
    assert second.count() == first.count()
    assert second.puzzle_at(0).moves == first.puzzle_at(0).moves
