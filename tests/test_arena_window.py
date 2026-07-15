from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import chess

from chess_puzzles.app.main_window import MainWindow
from chess_puzzles.app.refutation_playback import RefutationPlayback
from chess_puzzles.puzzle import Puzzle, PuzzleSession
from chess_puzzles.store import ContentDatabase, ContentMeta, DECK_KIND_ARENA, UserStore, now_iso


class _Var:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


def _puzzle(puzzle_id: str = "p1", rating: str = "1500") -> Puzzle:
    return Puzzle(
        title="Two moves",
        initial_fen=chess.STARTING_FEN,
        moves=(chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5"), chess.Move.from_uci("g1f3")),
        puzzle_id=puzzle_id,
        headers={"Rating": rating},
    )


def _window(tmp_path: Path, puzzle: Puzzle) -> MainWindow:
    window = MainWindow.__new__(MainWindow)
    window.session = PuzzleSession(puzzle, chess.WHITE)
    window.waiting_for_continue = False
    window._engaged = False
    window._visit_recorded = False
    window._solve_clock_start = None
    window._carry_mistakes = 0
    window._carry_aids = 0
    window._arena_rating = None
    window.user_store = UserStore.open(tmp_path / "userdata.db")
    window.favorites_view = False
    window.review_view = False
    window.database = None
    window.database_path = None
    window._stats_anchor = "2026-01-01T00:00:00Z"
    window.current_index = 0
    window._show_session_stats_var = SimpleNamespace(get=lambda: True)
    window._session_stats_vars = {
        key: _Var() for key in ("Attempted", "Solved", "Total", "Average")
    }
    window._info_vars = {
        key: _Var() for key in ("Puzzle", "Move", "Turn", "Side", "Start", "Theme")
    }
    window._move_progress = _Var()
    window._layout = SimpleNamespace(
        board=SimpleNamespace(show_hint_square=lambda _square: None)
    )
    window._status_var = _Var()
    window._refutation_playback = RefutationPlayback(window)
    window._avoided_traps = []
    window._seen_refutations = set()
    return window


def _arena_deck(puzzles: list[Puzzle]) -> ContentDatabase:
    meta = ContentMeta(
        database_id="arena-test", name="Arena", created_at=now_iso(), updated_at=now_iso()
    )
    database = ContentDatabase.in_memory(meta, puzzles)
    database.set_meta_value("kind", DECK_KIND_ARENA)
    database.set_meta_value("arena.start_rating", "1500")
    return database


def test_hint_engages_the_visit_so_leaving_records_an_attempt(tmp_path: Path) -> None:
    window = _window(tmp_path, _puzzle())

    window.show_hint()
    window._finalize_visit()

    assert window._engaged is True
    rows = window.user_store.connection.execute(
        "SELECT outcome, aids, puzzle_rating FROM attempt"
    ).fetchall()
    assert [tuple(row) for row in rows] == [("gave_up", 1, 1500)]


def test_reset_preserves_mistake_evidence_in_every_training_mode(tmp_path: Path) -> None:
    window = _window(tmp_path, _puzzle())
    assert window.database is None  # ordinary/non-arena training semantics
    # Collaborators reset_position touches but this test does not exercise.
    window.cancel_computer_reply = lambda: None
    window.cancel_prefix_recap = lambda: None
    window._refresh_from_session = lambda *_args, **_kwargs: None
    window._schedule_computer_reply = lambda: None

    assert window.session.play_user_move(chess.Move.from_uci("a2a3")).name == "INCORRECT"
    window._engaged = True
    window.reset_position()
    assert window.session.mistakes == 0  # the run restarts...
    assert window._carry_mistakes == 1  # ...the visit remembers

    for uci in ("e2e4", "e7e5", "g1f3"):
        window.session.board.push(chess.Move.from_uci(uci))
        window.session.move_index += 1
    window._record_solve()

    rows = window.user_store.connection.execute(
        "SELECT outcome, mistakes, grade FROM attempt"
    ).fetchall()
    assert [tuple(row) for row in rows] == [("solved", 1, "hard")]


def test_leaving_untouched_arena_puzzle_prompts_and_records_loss(
    tmp_path: Path, monkeypatch
) -> None:
    window = _window(tmp_path, _puzzle())
    window.database = _arena_deck([_puzzle()])
    window.database_path = tmp_path / "arena.cpdb"
    window.root = SimpleNamespace()
    answers = iter([False, True])
    monkeypatch.setattr(
        "chess_puzzles.app.main_window.messagebox.askyesno",
        lambda *_args, **_kwargs: next(answers),
    )

    assert window._settle_current_arena_puzzle() is False  # cancel stays put
    assert window.user_store.deck_attempt_count("arena-test") == 0

    assert window._settle_current_arena_puzzle() is True  # confirm gives up
    rows = window.user_store.connection.execute(
        "SELECT outcome, grade, database_id, puzzle_rating FROM attempt"
    ).fetchall()
    assert [tuple(row) for row in rows] == [("gave_up", "again", "arena-test", 1500)]


def test_leaving_already_attempted_arena_puzzle_needs_no_prompt(tmp_path: Path) -> None:
    window = _window(tmp_path, _puzzle())
    window.database = _arena_deck([_puzzle()])
    window.database_path = tmp_path / "arena.cpdb"
    window._engaged = True
    window._finalize_visit()  # first visit gave up; puzzle now has an attempt

    window.session = PuzzleSession(_puzzle(), chess.WHITE)  # fresh untouched visit
    window._engaged = False
    window._visit_recorded = False

    # No monkeypatched askyesno: a prompt would crash the test.
    assert window._settle_current_arena_puzzle() is True
    assert window.user_store.deck_attempt_count("arena-test") == 1


def _wire_navigation(window: MainWindow) -> list[float]:
    """Stub next_puzzle collaborators; returns the ratings seen by refill."""
    ratings_at_refill: list[float] = []

    def fake_refill() -> int:
        ratings_at_refill.append(window._arena_rating)
        return 0  # empty refill: the recorded loss must survive

    window._arena_refill = fake_refill
    window._user_notes = SimpleNamespace(save_now=lambda: None)
    window.load_current_puzzle = lambda: None
    return ratings_at_refill


def test_engaged_boundary_loss_is_recorded_before_refill(tmp_path: Path) -> None:
    window = _window(tmp_path, _puzzle())
    window.database = _arena_deck([_puzzle()])  # one puzzle: we are at the end
    window.database_path = tmp_path / "arena.cpdb"
    ratings_at_refill = _wire_navigation(window)

    assert window.session.play_user_move(chess.Move.from_uci("a2a3")).name == "INCORRECT"
    window._engaged = True
    window.next_puzzle()

    rows = window.user_store.connection.execute(
        "SELECT outcome, mistakes FROM attempt"
    ).fetchall()
    assert [tuple(row) for row in rows] == [("gave_up", 1)]  # exactly once
    # The sampler ran after the loss: it saw the post-loss rating.
    assert ratings_at_refill == [1500 - 20]
    assert window._status_var.value == "No new puzzles available."


def test_hint_assisted_boundary_loss_is_recorded_before_refill(tmp_path: Path) -> None:
    window = _window(tmp_path, _puzzle())
    window.database = _arena_deck([_puzzle()])
    window.database_path = tmp_path / "arena.cpdb"
    ratings_at_refill = _wire_navigation(window)

    window.show_hint()  # engages the visit and counts an aid
    window.next_puzzle()

    rows = window.user_store.connection.execute("SELECT outcome, aids FROM attempt").fetchall()
    assert [tuple(row) for row in rows] == [("gave_up", 1)]
    assert ratings_at_refill == [1500 - 20]


def test_completed_boundary_puzzle_is_not_recorded_again_by_refill(tmp_path: Path) -> None:
    window = _window(tmp_path, _puzzle())
    window.database = _arena_deck([_puzzle()])
    window.database_path = tmp_path / "arena.cpdb"
    _wire_navigation(window)

    window._engaged = True
    for uci in ("e2e4", "e7e5", "g1f3"):
        window.session.board.push(chess.Move.from_uci(uci))
        window.session.move_index += 1
    window._record_solve()
    assert window.user_store.deck_attempt_count("arena-test") == 1

    window.next_puzzle()

    assert window.user_store.deck_attempt_count("arena-test") == 1


def _reset_fixture(tmp_path: Path, monkeypatch, *, delete_attempts: bool):
    """An arena at index 2 with only puzzle 'a' attempted; run a user-data
    reset through the real action with the dialog replaced by a stub."""
    from chess_puzzles.app.main_database_actions import MainDatabaseActions

    window = _window(tmp_path, _puzzle("a"))
    window.database = _arena_deck([_puzzle("a"), _puzzle("b"), _puzzle("c")])
    window.database_path = tmp_path / "arena.cpdb"
    window.root = SimpleNamespace()
    window._engaged = True
    window._finalize_visit()  # 'a' attempted; frontier is now 'b' (index 1)
    window.current_index = 2
    loads: list[int] = []
    window.load_current_puzzle = lambda: loads.append(window.current_index)
    window._refresh_session_stats = lambda: None

    def fake_dialog(_parent, store, *, database_id, deck_name, is_arena):
        assert is_arena
        class Stub:
            attempts_deleted = delete_attempts

            def show(self) -> bool:
                store.delete_deck_data(
                    database_id,
                    attempts=delete_attempts,
                    favorites=not delete_attempts,
                    position=False,
                )
                return True
        return Stub()

    monkeypatch.setattr(
        "chess_puzzles.app.main_database_actions.UserDataManagerDialog", fake_dialog
    )
    MainDatabaseActions(window).manage_userdata()
    return window, loads


def test_arena_attempt_reset_resumes_at_frontier(tmp_path: Path, monkeypatch) -> None:
    window, loads = _reset_fixture(tmp_path, monkeypatch, delete_attempts=True)
    assert window.current_index == 0  # everything unattempted again
    assert loads == [0]


def test_favorites_only_reset_does_not_move_the_user(tmp_path: Path, monkeypatch) -> None:
    window, loads = _reset_fixture(tmp_path, monkeypatch, delete_attempts=False)
    assert window.current_index == 2  # frontier would be 1; we must not jump
    assert loads == [2]


def test_review_resolve_does_not_move_arena_rating(tmp_path: Path) -> None:
    from chess_puzzles.arena import session_rating

    window = _window(tmp_path, _puzzle())
    window.database = _arena_deck([_puzzle()])
    window.database_path = tmp_path / "arena.cpdb"
    window._engaged = True
    window._finalize_visit()  # rated first attempt: a loss

    connection = window.user_store.connection
    after_loss = session_rating(connection, "arena-test", 1500)
    assert after_loss == 1500 - 20

    # Later review re-solve of the same puzzle (recorded against the arena).
    window.session = PuzzleSession(_puzzle(), chess.WHITE)
    window._engaged = True
    window._visit_recorded = False
    for uci in ("e2e4", "e7e5", "g1f3"):
        window.session.board.push(chess.Move.from_uci(uci))
        window.session.move_index += 1
    window._record_solve()

    assert session_rating(connection, "arena-test", 1500) == after_loss
