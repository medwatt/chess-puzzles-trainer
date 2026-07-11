from __future__ import annotations

import chess

from chess_puzzles.puzzle import MoveResult, Puzzle, PuzzleSession


def test_puzzle_session_validates_mainline_moves() -> None:
    puzzle = Puzzle(
        title="Mate threat",
        initial_fen=chess.STARTING_FEN,
        moves=(chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")),
    )
    session = PuzzleSession(puzzle, chess.WHITE)

    assert session.play_user_move(chess.Move.from_uci("d2d4")) is MoveResult.INCORRECT
    assert session.board.fullmove_number == 1

    assert session.play_user_move(chess.Move.from_uci("e2e4")) is MoveResult.CORRECT
    assert session.play_user_move(chess.Move.from_uci("g1f3")) is MoveResult.WAITING
    assert session.play_computer_move() == chess.Move.from_uci("e7e5")
    assert session.is_complete


def test_skip_first_move_is_controller_policy_not_session_auto_play() -> None:
    puzzle = Puzzle(
        title="Skip",
        initial_fen=chess.STARTING_FEN,
        moves=(chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")),
        skip_first_move=True,
    )

    session = PuzzleSession(puzzle, chess.BLACK)

    assert session.move_index == 0
    assert session.board.piece_at(chess.E4) is None
    assert session.play_computer_move() == chess.Move.from_uci("e2e4")
    assert session.play_user_move(chess.Move.from_uci("e7e5")) is MoveResult.COMPLETE


TREE_PGN = """[Event "Tree"]
[Result "*"]

1. e4 {main} ( 1. d4 {alt} 1... d5 ) ( 1. f3 $4 {weakens} 1... e5 2. g4 $4
Qh4# {mate} ) 1... e5 *
"""


def _tree_puzzle() -> Puzzle:
    return Puzzle(
        title="Tree",
        initial_fen=chess.STARTING_FEN,
        moves=(chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")),
        pgn_text=TREE_PGN,
    )


def test_marked_variation_is_a_blunder_with_refutation() -> None:
    session = PuzzleSession(_tree_puzzle(), chess.WHITE)

    assert session.play_user_move(chess.Move.from_uci("f2f3")) is MoveResult.BLUNDER
    assert session.mistakes == 1
    assert session.board.fullmove_number == 1  # blunder is not played

    refutation = session.last_refutation
    assert refutation is not None
    assert refutation.move == chess.Move.from_uci("f2f3")
    assert [m.uci() for m in refutation.line] == ["e7e5", "g2g4", "d8h4"]
    assert refutation.comments[0] == "weakens"

    # The session is still solvable afterwards, and the refutation clears.
    assert session.play_user_move(chess.Move.from_uci("e2e4")) is MoveResult.CORRECT
    assert session.last_refutation is None


def test_unmarked_sibling_line_is_an_alternative_not_a_mistake() -> None:
    session = PuzzleSession(_tree_puzzle(), chess.WHITE)

    assert session.play_user_move(chess.Move.from_uci("d2d4")) is MoveResult.ALTERNATIVE
    assert session.mistakes == 0
    assert session.board.fullmove_number == 1  # not played; the drilled line continues

    assert session.play_user_move(chess.Move.from_uci("b1c3")) is MoveResult.INCORRECT
    assert session.mistakes == 1


def test_puzzle_without_pgn_text_keeps_original_behavior() -> None:
    puzzle = Puzzle(
        title="No tree",
        initial_fen=chess.STARTING_FEN,
        moves=(chess.Move.from_uci("e2e4"),),
    )
    session = PuzzleSession(puzzle, chess.WHITE)

    # Every legal deviation is plain INCORRECT when there is no tree.
    assert session.play_user_move(chess.Move.from_uci("d2d4")) is MoveResult.INCORRECT
    assert session.play_user_move(chess.Move.from_uci("f2f3")) is MoveResult.INCORRECT
    assert session.last_refutation is None


def test_reset_restores_tree_cursor() -> None:
    session = PuzzleSession(_tree_puzzle(), chess.WHITE)
    assert session.play_user_move(chess.Move.from_uci("e2e4")) is MoveResult.CORRECT
    session.reset()

    # After reset the cursor is back at the root: the root's marked sibling
    # is a blunder again rather than an off-tree incorrect move.
    assert session.play_user_move(chess.Move.from_uci("f2f3")) is MoveResult.BLUNDER


def test_session_counts_incorrect_moves_and_reset_clears_them() -> None:
    puzzle = Puzzle(
        title="Mistakes",
        initial_fen=chess.STARTING_FEN,
        moves=(chess.Move.from_uci("e2e4"),),
    )
    session = PuzzleSession(puzzle, chess.WHITE)

    assert session.play_user_move(chess.Move.from_uci("d2d4")) is MoveResult.INCORRECT
    assert session.play_user_move(chess.Move.from_uci("e2e5")) is MoveResult.ILLEGAL
    assert session.play_user_move(chess.Move.from_uci("g1f3")) is MoveResult.INCORRECT
    assert session.mistakes == 2

    session.reset()
    assert session.mistakes == 0
    assert session.play_user_move(chess.Move.from_uci("e2e4")) is MoveResult.COMPLETE
    assert session.mistakes == 0
