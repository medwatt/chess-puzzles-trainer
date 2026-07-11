from __future__ import annotations

import chess

from chess_puzzles.puzzle.tree import MoveTree


ANNOTATED_PGN = """[Event "Tree"]
[Result "*"]

1. e4 $1 {main} ( 1. d4 {alt} 1... d5 ) ( 1. f3 $4 {weakens} 1... e5 2. g4 $4
Qh4# {mate} ) 1... e5 *
"""


def test_tree_classifies_mainline_alternative_and_mistake() -> None:
    tree = MoveTree.from_pgn_text(ANNOTATED_PGN, chess.STARTING_FEN)
    assert tree is not None
    assert tree.has_branches

    root = tree.root
    main = root.child(chess.Move.from_uci("e2e4"))
    alt = root.child(chess.Move.from_uci("d2d4"))
    bad = root.child(chess.Move.from_uci("f2f3"))
    assert main is not None and not main.is_mistake
    assert alt is not None and not alt.is_mistake
    assert bad is not None and bad.is_mistake
    assert root.child(chess.Move.from_uci("b1c3")) is None


def test_refutation_carries_line_and_comments() -> None:
    tree = MoveTree.from_pgn_text(ANNOTATED_PGN, chess.STARTING_FEN)
    assert tree is not None
    bad = tree.root.child(chess.Move.from_uci("f2f3"))
    assert bad is not None

    refutation = MoveTree.refutation_of(bad)
    assert refutation.move == chess.Move.from_uci("f2f3")
    assert [m.uci() for m in refutation.line] == ["e7e5", "g2g4", "d8h4"]
    assert refutation.comments[0] == "weakens"
    assert refutation.comments[-1] == "mate"


def test_tree_absent_for_empty_or_mismatched_pgn() -> None:
    assert MoveTree.from_pgn_text("", chess.STARTING_FEN) is None
    assert MoveTree.from_pgn_text("   \n", chess.STARTING_FEN) is None
    # PGN that starts from a different position does not describe the puzzle.
    other_fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
    assert MoveTree.from_pgn_text(ANNOTATED_PGN, other_fen) is None


def test_null_move_children_are_dropped() -> None:
    pgn = '[Event "Text page"]\n[Result "*"]\n\n{lesson} 1. -- {more text} *\n'
    tree = MoveTree.from_pgn_text(pgn, chess.STARTING_FEN)
    assert tree is not None
    assert tree.root.children == ()
    assert not tree.has_branches


def test_linear_game_has_no_branches() -> None:
    pgn = '[Event "Line"]\n[Result "*"]\n\n1. e4 e5 2. Nf3 *\n'
    tree = MoveTree.from_pgn_text(pgn, chess.STARTING_FEN)
    assert tree is not None
    assert not tree.has_branches
