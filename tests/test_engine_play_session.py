import chess

from chess_puzzles.engine.play_session import EnginePlaySession


def test_user_can_move_for_either_side() -> None:
    session = EnginePlaySession(chess.Board(), chess.WHITE)
    assert session.play_user_move(chess.Move.from_uci("e2e4")) is not None
    # Forcing a move for the engine's side is allowed.
    assert session.play_user_move(chess.Move.from_uci("e7e5")) is not None
    assert session.is_human_turn


def test_illegal_moves_rejected() -> None:
    session = EnginePlaySession(chess.Board(), chess.WHITE)
    assert session.play_user_move(chess.Move.from_uci("e2e5")) is None
    # Own piece cannot move when it is not that side's turn.
    session.play_user_move(chess.Move.from_uci("e2e4"))
    assert session.play_user_move(chess.Move.from_uci("d2d4")) is None


def test_takeback_restores_position() -> None:
    session = EnginePlaySession(chess.Board(), chess.WHITE)
    session.play_user_move(chess.Move.from_uci("e2e4"))
    session.play_user_move(chess.Move.from_uci("e7e5"))
    assert session.takeback() == chess.Move.from_uci("e7e5")
    assert session.takeback() == chess.Move.from_uci("e2e4")
    assert session.takeback() is None
    assert session.board.fen() == chess.Board().fen()
