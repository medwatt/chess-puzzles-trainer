"""Turn handling in the play-vs-engine window.

The window is driven through EnginePlaySession plus the auto-reply flag, so
these exercise the decision logic (``_continue_after_move`` and friends)
against a stub window rather than a real Toplevel.
"""

from __future__ import annotations

import chess

from chess_puzzles.engine.play_session import EnginePlaySession
from chess_puzzles.engine.play_window import EnginePlayWindow
from chess_puzzles.shortcuts import ENGINE_MOVE_KEY

E4 = chess.Move.from_uci("e2e4")
E5 = chess.Move.from_uci("e7e5")
NF3 = chess.Move.from_uci("g1f3")


class _Var:
    def __init__(self, value) -> None:
        self.value = value

    def get(self):
        return self.value

    def set(self, value) -> None:
        self.value = value


class _Button:
    def __init__(self) -> None:
        self.state = "normal"

    def configure(self, state: str) -> None:
        self.state = state


class FakeWindow:
    """Just the collaborators the turn logic touches."""

    def __init__(self, auto_reply: bool = True) -> None:
        self.session = EnginePlaySession(chess.Board(), chess.WHITE)
        self._auto_reply_var = _Var(auto_reply)
        self.status_var = _Var("")
        self._engine_move_button = _Button()
        self._thinking = False
        self.scheduled = 0
        self.analysed = 0

    # -- the real methods under test ------------------------------------
    _continue_after_move = EnginePlayWindow._continue_after_move
    _turn_status = EnginePlayWindow._turn_status
    _set_status = EnginePlayWindow._set_status
    _engine_can_move = EnginePlayWindow._engine_can_move
    _game_over_text = EnginePlayWindow._game_over_text
    _on_auto_reply_changed = EnginePlayWindow._on_auto_reply_changed
    _begin_thinking = EnginePlayWindow._begin_thinking

    # -- stubbed collaborators ------------------------------------------
    def _schedule_engine_move(self) -> None:
        self.scheduled += 1
        self._begin_thinking()

    def _request_position_analysis(self) -> None:
        self.analysed += 1

    def _cancel_engine(self) -> None:
        self._thinking = False


def test_auto_reply_hands_the_turn_to_the_engine() -> None:
    window = FakeWindow(auto_reply=True)
    window.session.play_user_move(E4)

    window._continue_after_move()

    assert window.scheduled == 1
    assert "thinking" in window.status_var.get()


def test_without_auto_reply_the_position_just_waits() -> None:
    window = FakeWindow(auto_reply=False)
    window.session.play_user_move(E4)

    window._continue_after_move()

    assert window.scheduled == 0
    assert window.analysed == 1, "the waiting position is still analysed"
    assert window.status_var.get() == (
        f"Engine's turn - press {ENGINE_MOVE_KEY} for its move, or play it yourself."
    )


def test_playing_both_sides_needs_no_takeback() -> None:
    # The point of the mode: three plies, no engine move, no undo.
    window = FakeWindow(auto_reply=False)
    for move in (E4, E5, NF3):
        assert window.session.play_user_move(move) is not None
        window._continue_after_move()

    assert window.scheduled == 0
    assert [m.uci() for m in window.session.board.move_stack] == ["e2e4", "e7e5", "g1f3"]


def test_engine_move_button_is_enabled_only_on_the_engines_turn() -> None:
    window = FakeWindow(auto_reply=False)
    window._continue_after_move()
    assert window._engine_move_button.state == "disabled", "your move"

    window.session.play_user_move(E4)
    window._continue_after_move()
    assert window._engine_move_button.state == "normal", "engine's move"

    window._thinking = True
    window._set_status("Engine thinking...")
    assert window._engine_move_button.state == "disabled", "already thinking"


def test_turning_auto_reply_back_on_lets_the_engine_catch_up() -> None:
    window = FakeWindow(auto_reply=False)
    window.session.play_user_move(E4)
    window._continue_after_move()
    assert window.scheduled == 0

    window._auto_reply_var.set(True)
    window._on_auto_reply_changed()

    assert window.scheduled == 1


def test_a_finished_game_never_schedules_or_enables() -> None:
    window = FakeWindow(auto_reply=True)
    window.session.board = chess.Board(
        "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
    )
    assert window.session.board.is_game_over()

    window._continue_after_move()

    assert window.scheduled == 0
    assert window._engine_move_button.state == "disabled"
    assert "Game over" in window.status_var.get()
