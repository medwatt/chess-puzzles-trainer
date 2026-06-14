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
