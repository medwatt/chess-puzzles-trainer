from __future__ import annotations

from chess_puzzles.lichess import LichessCsvImporter, LichessImportCriteria


def test_lichess_importer_filters_and_builds_puzzles(tmp_path) -> None:
    path = tmp_path / "lichess.csv"
    path.write_text(
        "PuzzleId,FEN,Moves,Rating,Popularity,Themes,GameUrl\n"
        "abc,8/8/8/8/8/8/4K3/7k w - - 0 1,e2e3,1200,95,endgame mate,\n"
        "def,8/8/8/8/8/8/4K3/7k w - - 0 1,e2e4,2400,10,fork,\n",
        encoding="utf-8",
    )

    importer = LichessCsvImporter()
    puzzles = importer.sample_puzzles(
        path,
        LichessImportCriteria(sample_size=5, rating_min=1000, rating_max=1300, popularity_min=50),
        seed=1,
    )

    assert len(puzzles) == 1
    assert puzzles[0].puzzle_id == "abc"
    assert puzzles[0].skip_first_move
