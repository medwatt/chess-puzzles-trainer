from __future__ import annotations

from dataclasses import replace
from io import StringIO

import chess

from chess_puzzles.pgn import PgnLoader
from chess_puzzles.pgn.utils import pgn_for_puzzle


def test_pgn_loader_preserves_headers_comments_and_text() -> None:
    pgn = """
[Event "Training"]
[White "Alpha"]
[Black "Beta"]
[PuzzleSide "White"]

1. e4 {first} e5 {reply} 2. Nf3 *
"""

    puzzles = PgnLoader().load(StringIO(pgn))

    assert len(puzzles) == 1
    puzzle = puzzles[0]
    assert puzzle.title == "Training - Alpha: Beta"
    assert puzzle.player_color == chess.WHITE
    assert puzzle.moves == (
        chess.Move.from_uci("e2e4"),
        chess.Move.from_uci("e7e5"),
        chess.Move.from_uci("g1f3"),
    )
    assert puzzle.comments[1] == "first"
    assert "Training" in puzzle.pgn_text


def test_pgn_loader_recovers_moves_after_blank_line_in_movetext() -> None:
    # Some exporters emit a blank line between a leading comment and the first
    # move. Without handling it, python-chess ends the game at the blank line
    # (zero moves) and parses the moves as a phantom headerless game.
    pgn = """
[Event "Quiz"]
[Black "Puzzle 47"]
[SetUp "1"]
[FEN "6k1/7p/2pr2p1/p3ppP1/P4n1P/1PB2P2/5K2/R7 w - - 1 38"]

{Black has an extra pawn. Can White equalise?}

38. Bxa5 Nd3+ 39. Kf1 *

[Event "Quiz"]
[Black "Puzzle 48"]

1. e4 *
"""

    puzzles = PgnLoader().load(StringIO(pgn))

    assert len(puzzles) == 2  # no phantom game from the split
    first = puzzles[0]
    assert first.moves[0] == chess.Move.from_uci("c3a5")  # Bxa5 recovered
    assert first.comments[0] == "Black has an extra pawn. Can White equalise?"


def test_pgn_loader_keeps_blank_lines_inside_comments() -> None:
    pgn = """
[Event "Training"]

1. e4 {line one

line two} e5 *
"""

    puzzle = PgnLoader().load(StringIO(pgn))[0]

    assert puzzle.moves == (
        chess.Move.from_uci("e2e4"),
        chess.Move.from_uci("e7e5"),
    )
    assert "line one" in puzzle.comments[1] and "line two" in puzzle.comments[1]


def test_pgn_loader_handles_multiple_and_midgame_blank_lines() -> None:
    pgn = """
[Event "Quiz"]

{intro}


1. e4 e5

2. Nf3 Nc6 *
"""

    puzzle = PgnLoader().load(StringIO(pgn))[0]

    assert puzzle.moves == tuple(
        chess.Move.from_uci(u) for u in ("e2e4", "e7e5", "g1f3", "b8c6")
    )


def test_pgn_loader_recovers_after_unbalanced_nested_brace_in_earlier_game() -> None:
    # PGN comments do not nest: a stray '{' inside a comment is literal text and
    # the comment still ends at the first '}'. A nesting counter would stay stuck
    # "inside a comment" for the rest of the file and stop fixing later games.
    pgn = """
[Event "A"]

{a note with a stray { brace and one close}

1. d4 *

[Event "B"]

{prompt}

1. e4 e5 *
"""

    puzzles = PgnLoader().load(StringIO(pgn))

    assert len(puzzles) == 2  # game B not split into a phantom
    assert puzzles[1].moves == (
        chess.Move.from_uci("e2e4"),
        chess.Move.from_uci("e7e5"),
    )


def test_pgn_loader_does_not_miscount_braces_in_headers_or_semicolon_comments() -> None:
    # A '{' in a header value or after a ';' line comment must not be mistaken
    # for the start of a real comment, which would suspend blank-line removal.
    pgn = """
[Event "Quiz {not a comment"]
[Annotator "a } b"]

{intro}

1. e4 ; trailing { brace

2. e5 *
"""

    puzzle = PgnLoader().load(StringIO(pgn))[0]

    assert puzzle.moves == (
        chess.Move.from_uci("e2e4"),
        chess.Move.from_uci("e7e5"),
    )


def test_pgn_loader_drops_null_move_but_keeps_its_text() -> None:
    # Some course pages are written as a "1. --" null move with the lesson text
    # as its comment. The pass must not be stored as a 0000 solution move, and
    # its text must survive (here it sits after the null move).
    pgn = """
[Event "Lesson"]

1. -- {Here is the lesson text.} *
"""

    puzzle = PgnLoader().load(StringIO(pgn))[0]

    assert puzzle.moves == ()  # no 0000 pass move
    assert puzzle.comments[0] == "Here is the lesson text."


def test_pgn_loader_folds_null_move_text_into_leading_comment() -> None:
    pgn = """
[Event "Lesson"]

{Intro paragraph.} 1. -- {Trailing note.} *
"""

    puzzle = PgnLoader().load(StringIO(pgn))[0]

    assert puzzle.moves == ()
    assert puzzle.comments == ("Intro paragraph.\n\nTrailing note.",)


def test_pgn_loader_drops_content_free_games_but_keeps_study_pages() -> None:
    pgn = """
[Event "Real"]

1. e4 e5 *

[Event "Study"]

{Just think about this position.} *

[Event "Empty"]
[White "?"]

*
"""

    puzzles = PgnLoader().load(StringIO(pgn))

    # The header-only game is dropped; the move-free but commented study page stays.
    assert [p.headers["Event"] for p in puzzles] == ["Real", "Study"]
    assert puzzles[1].moves == ()
    assert puzzles[1].comments[0] == "Just think about this position."


def test_pgn_for_puzzle_rebuild_keeps_comments_on_their_moves() -> None:
    pgn = """
[Event "Training"]

{before} 1. e4 {first} e5 {reply} *
"""
    puzzle = PgnLoader().load(StringIO(pgn))[0]
    # Force the rebuild path by dropping the stored PGN text.
    rebuilt = pgn_for_puzzle(replace(puzzle, pgn_text=""))

    reparsed = PgnLoader().load(StringIO(rebuilt))[0]
    assert reparsed.comments == puzzle.comments
