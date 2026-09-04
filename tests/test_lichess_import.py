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


def _opening_csv(tmp_path):
    """Three puzzles: a Najdorf, another Sicilian, and an untagged one.

    Mirrors the real file, where every tagged row carries both its family and
    its variation and ~80% of rows carry neither."""
    path = tmp_path / "openings.csv"
    path.write_text(
        "PuzzleId,FEN,Moves,Rating,Popularity,Themes,GameUrl,OpeningTags\n"
        "naj,8/8/8/8/8/8/4K3/7k w - - 0 1,e2e3,1500,90,fork middlegame,,"
        "Sicilian_Defense Sicilian_Defense_Najdorf_Variation\n"
        "dra,8/8/8/8/8/8/4K3/7k w - - 0 1,e2e4,1500,90,pin middlegame,,"
        "Sicilian_Defense Sicilian_Defense_Dragon_Variation\n"
        "none,8/8/8/8/8/8/4K3/7k w - - 0 1,e2d3,1500,90,fork endgame,,\n",
        encoding="utf-8",
    )
    return path


def _ids(importer, path, **kwargs):
    criteria = LichessImportCriteria(sample_size=10, **kwargs)
    return sorted(p.puzzle_id for p in importer.sample_puzzles(path, criteria, seed=1))


def test_opening_family_matches_every_variation_under_it(tmp_path) -> None:
    path = _opening_csv(tmp_path)
    importer = LichessCsvImporter()

    assert _ids(importer, path, openings=("Sicilian_Defense",)) == ["dra", "naj"]
    assert _ids(importer, path, openings=("Sicilian_Defense_Najdorf_Variation",)) == ["naj"]


def test_themes_and_openings_are_independent_dimensions(tmp_path) -> None:
    """Empty means any; both set means both must hold."""
    path = _opening_csv(tmp_path)
    importer = LichessCsvImporter()

    # Neither filter: everything.
    assert _ids(importer, path) == ["dra", "naj", "none"]
    # Theme only: the untagged puzzle still qualifies.
    assert _ids(importer, path, themes=("fork",)) == ["naj", "none"]
    # Opening only: theme is unconstrained.
    assert _ids(importer, path, openings=("Sicilian_Defense",)) == ["dra", "naj"]
    # Both: the intersection, so the untagged fork drops out.
    assert _ids(importer, path, themes=("fork",), openings=("Sicilian_Defense",)) == ["naj"]
    # Both set but disjoint: nothing.
    assert _ids(importer, path, themes=("endgame",), openings=("Sicilian_Defense",)) == []


def _quality_csv(tmp_path):
    """Rows differing only in the columns the quality filters read."""
    path = tmp_path / "quality.csv"
    path.write_text(
        "PuzzleId,FEN,Moves,Rating,RatingDeviation,Popularity,NbPlays,Themes,GameUrl,OpeningTags\n"
        # settled rating, heavily played, one move (2 plies)
        "settled,8/8/8/8/8/8/4K3/7k w - - 0 1,e2e3 e2e4,1500,75,90,5000,fork,,\n"
        # unsettled rating, barely played, three of your moves (6 plies)
        "raw,8/8/8/8/8/8/4K3/7k w - - 0 1,e2e3 e2e4 e2d3 d3c4 c4b5 b5a6,1500,300,90,3,fork,,\n",
        encoding="utf-8",
    )
    return path


def test_rating_deviation_and_play_count_gates(tmp_path) -> None:
    path = _quality_csv(tmp_path)
    importer = LichessCsvImporter()

    assert _ids(importer, path) == ["raw", "settled"]
    assert _ids(importer, path, rating_deviation_max=80) == ["settled"]
    assert _ids(importer, path, nb_plays_min=100) == ["settled"]


def test_move_count_is_measured_in_your_moves(tmp_path) -> None:
    """The CSV's move list opens with the opponent's setup move."""
    path = _quality_csv(tmp_path)
    importer = LichessCsvImporter()

    assert _ids(importer, path, moves_min=2) == ["raw"]
    assert _ids(importer, path, moves_max=1) == ["settled"]
    assert _ids(importer, path, moves_min=3, moves_max=3) == ["raw"]


def test_theme_mode_and_exclusions(tmp_path) -> None:
    path = tmp_path / "themes.csv"
    path.write_text(
        "PuzzleId,FEN,Moves,Rating,Popularity,Themes,GameUrl,OpeningTags\n"
        "both,8/8/8/8/8/8/4K3/7k w - - 0 1,e2e3,1500,90,fork endgame,,\n"
        "one,8/8/8/8/8/8/4K3/7k w - - 0 1,e2e4,1500,90,fork middlegame,,\n"
        "trivial,8/8/8/8/8/8/4K3/7k w - - 0 1,e2d3,1500,90,fork oneMove,,\n",
        encoding="utf-8",
    )
    importer = LichessCsvImporter()

    picks = ("fork", "endgame")
    assert _ids(importer, path, themes=picks) == ["both", "one", "trivial"]
    assert _ids(importer, path, themes=picks, theme_mode="all") == ["both"]
    assert _ids(importer, path, themes=("fork",), themes_excluded=("oneMove",)) == ["both", "one"]
    # Exclusion works with no include list at all.
    assert _ids(importer, path, themes_excluded=("endgame", "oneMove")) == ["one"]


def test_scan_reports_progress_and_honours_cancellation(tmp_path) -> None:
    path = _quality_csv(tmp_path)
    seen: list[tuple[int, int]] = []
    puzzles = LichessCsvImporter().sample_puzzles(
        path,
        LichessImportCriteria(sample_size=10),
        seed=1,
        on_progress=lambda examined, accepted: seen.append((examined, accepted)),
        should_stop=lambda: len(seen) >= 1,
    )

    assert seen, "progress must be reported per row"
    # Stopping keeps whatever matched before the stop, rather than discarding it.
    assert len(puzzles) <= 1


def test_wraparound_pass_stops_at_the_shortfall(tmp_path) -> None:
    """The second pass must count what the first already accepted.

    Starting from a random offset, a scan that reaches EOF short of the
    sample wraps to the top of the file. Counting only that pass made it hunt
    for a whole fresh sample, so it over-scanned and reported more matches
    than were asked for ("found 110 of 100") before truncating the result.
    """
    path = tmp_path / "many.csv"
    rows = ["PuzzleId,FEN,Moves,Rating,Popularity,Themes,GameUrl,OpeningTags"]
    rows += [f"p{i:04},8/8/8/8/8/8/4K3/7k w - - 0 1,e2e3,1500,90,fork,," for i in range(400)]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    importer = LichessCsvImporter()

    # Several seeds, because only offsets landing near EOF wrap around.
    for seed in range(25):
        reported: list[int] = []
        puzzles = importer.sample_puzzles(
            path,
            LichessImportCriteria(sample_size=100),
            seed=seed,
            on_progress=lambda _examined, accepted: reported.append(accepted),
        )
        assert len(puzzles) == 100
        assert max(reported, default=0) <= 100, (
            f"seed {seed} reported {max(reported)} matches for a sample of 100"
        )
