from __future__ import annotations

import io

import chess
import chess.pgn

from chess_puzzles.pgn.loader import PgnLoader
from chess_puzzles.pgn.repertoire import ImportChoices, profile_games


def _games(pgn_text: str) -> list[chess.pgn.Game]:
    stream = io.StringIO(pgn_text)
    games = []
    while True:
        game = chess.pgn.read_game(stream)
        if game is None:
            return games
        games.append(game)


WHITE_REPERTOIRE = """
[Event "Course"]
[White "Chapter One"]
[Black "Main line"]
[Result "*"]

1. e4 e5 2. Nf3 (2. f4 exf4 3. Nf3) 2... Nc6 3. Bb5 *

[Event "Course"]
[White "Chapter One"]
[Black "Sicilian sideline"]
[Result "*"]

1. e4 c5 2. Nc3 Nc6 3. g3 *

[Event "Course"]
[White "Chapter Two"]
[Black "French"]
[Result "*"]

1. e4 e6 2. d4 d5 3. Nc3 *
"""


BLACK_REPERTOIRE = """
[Event "?"]
[White "Chapter"]
[Black "?"]
[Result "*"]

1. e4 c6 2. d4 (2. Nc3 d5 3. Nf3 dxe4) 2... d5 3. e5 Bf5 *
"""


def test_trained_side_white_when_lines_end_on_white_moves() -> None:
    profile = profile_games(_games(WHITE_REPERTOIRE))

    assert profile.trained_side == chess.WHITE
    assert profile.white_finishers == 4
    assert profile.black_finishers == 0


def test_trained_side_black_when_lines_end_on_black_moves() -> None:
    profile = profile_games(_games(BLACK_REPERTOIRE))

    assert profile.trained_side == chess.BLACK


def test_trained_side_none_without_evidence() -> None:
    assert profile_games([]).trained_side is None


def test_mistake_variations_do_not_count_as_finishers() -> None:
    pgn = """
[Event "?"]
[Result "*"]

1. e4 e5 (1... f6 $2 2. Qh5+ g6 3. Qxg6+) 2. Nf3 *
"""
    profile = profile_games(_games(pgn))

    # Only the mainline leaf (ending on White's 2. Nf3) counts; the ?-marked
    # 1...f6 refutation line is punish-content, not a drillable line.
    assert profile.white_finishers == 1
    assert profile.black_finishers == 0


def test_naming_suggests_repeating_field_as_chapter_and_varying_as_title() -> None:
    profile = profile_games(_games(WHITE_REPERTOIRE))

    assert profile.chapter_field == "White"
    assert profile.title_field == "Black"


def test_naming_single_game_falls_back_to_single_chapter() -> None:
    pgn = """
[Event "?"]
[White "Caro Kann"]
[Black "?"]
[Result "*"]

1. e4 c6 2. d4 (2. Nc3 d5) 2... d5 *
"""
    profile = profile_games(_games(pgn))

    assert profile.chapter_field == "White"
    assert profile.title_field == ""


def test_loader_applies_trained_side_and_naming() -> None:
    choices = ImportChoices(trained_side=chess.WHITE, chapter_field="White", title_field="Black")
    puzzles = PgnLoader().load(io.StringIO(WHITE_REPERTOIRE), split_lines=True, choices=choices)

    assert all(puzzle.player_color == chess.WHITE for puzzle in puzzles)
    assert {puzzle.theme for puzzle in puzzles} == {"Chapter One", "Chapter Two"}
    titles = [puzzle.title for puzzle in puzzles]
    assert titles[0].startswith("Main line (line 1/2)")
    assert "Sicilian sideline" in titles[2]


def test_loader_trained_side_black_survives_explicit_none_headers() -> None:
    # chess.BLACK is falsy; make sure the override is not lost to an `or`.
    choices = ImportChoices(trained_side=chess.BLACK)
    puzzles = PgnLoader().load(io.StringIO(BLACK_REPERTOIRE), split_lines=True, choices=choices)

    assert puzzles and all(puzzle.player_color == chess.BLACK for puzzle in puzzles)


def test_explicit_side_header_beats_import_choice() -> None:
    pgn = """
[Event "?"]
[TrainingSide "black"]
[Result "*"]

1. e4 e5 2. Nf3 *
"""
    choices = ImportChoices(trained_side=chess.WHITE)
    puzzles = PgnLoader().load(io.StringIO(pgn), split_lines=True, choices=choices)

    assert puzzles[0].player_color == chess.BLACK


def test_default_choices_change_nothing() -> None:
    plain = PgnLoader().load(io.StringIO(WHITE_REPERTOIRE), split_lines=True)
    with_default = PgnLoader().load(io.StringIO(WHITE_REPERTOIRE), split_lines=True, choices=ImportChoices())

    assert [(p.title, p.theme, p.player_color) for p in plain] == [
        (p.title, p.theme, p.player_color) for p in with_default
    ]
