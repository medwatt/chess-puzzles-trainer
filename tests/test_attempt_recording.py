from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import chess

from chess_puzzles.app.main_window import MainWindow
from chess_puzzles.puzzle import Puzzle, PuzzleSession
from chess_puzzles.store import UserStore


class _Var:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


def test_assisted_user_move_then_leave_records_gave_up(tmp_path: Path) -> None:
    puzzle = Puzzle(
        title="Two moves",
        initial_fen=chess.STARTING_FEN,
        moves=(chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5"), chess.Move.from_uci("g1f3")),
        puzzle_id="p1",
    )
    user_store = UserStore.open(tmp_path / "userdata.db")
    window = MainWindow.__new__(MainWindow)
    window.session = PuzzleSession(puzzle, chess.WHITE)
    window.waiting_for_continue = False
    window._engaged = False
    window._visit_recorded = False
    window._solve_clock_start = None
    window.user_store = user_store
    window._stats_anchor = "2026-01-01T00:00:00Z"
    window._show_session_stats_var = SimpleNamespace(get=lambda: True)
    window._session_stats_vars = {key: _Var() for key in ("Attempted", "Solved", "Total", "Average")}
    window._layout = SimpleNamespace(board=SimpleNamespace())
    window._status_var = SimpleNamespace(set=lambda _value: None)
    window._apply_correct_move = lambda result, move, board_before, status: None

    window.play_next_move_for_user()
    window._finalize_visit()

    assert window._engaged is True
    rows = user_store.connection.execute("SELECT outcome, aids FROM attempt").fetchall()
    assert [tuple(row) for row in rows] == [("gave_up", 1)]
    assert window._session_stats_vars["Attempted"].value == "1"
    assert window._session_stats_vars["Solved"].value == "0 (0%)"
    assert window._session_stats_vars["Total"].value == "0:00"
    assert window._session_stats_vars["Average"].value == "0:00"
