from __future__ import annotations

import chess

from chess_puzzles.puzzle.skip import infer_skip_first_move


WHITE_TO_MOVE = "8/8/8/8/8/8/4K3/7k w - - 0 1"


def _moves(*ucis: str) -> tuple[chess.Move, ...]:
    return tuple(chess.Move.from_uci(uci) for uci in ucis)


def test_no_moves_never_skips() -> None:
    assert infer_skip_first_move(WHITE_TO_MOVE, (), chess.WHITE) is False


def test_known_color_skips_when_opponent_to_move() -> None:
    assert infer_skip_first_move(WHITE_TO_MOVE, _moves("e2e3"), chess.WHITE) is False
    assert infer_skip_first_move(WHITE_TO_MOVE, _moves("e2e3"), chess.BLACK) is True


def test_unknown_color_uses_parity() -> None:
    assert infer_skip_first_move(WHITE_TO_MOVE, _moves("e2e3", "h1g1"), None) is True
    assert infer_skip_first_move(WHITE_TO_MOVE, _moves("e2e3", "h1g1", "e3e4"), None) is False
