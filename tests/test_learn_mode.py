from __future__ import annotations

import chess

from chess_puzzles.app.main_window import MainWindow
from chess_puzzles.app.refutation_playback import RefutationPlayback
from chess_puzzles.puzzle import Puzzle, PuzzleSession
from chess_puzzles.store import Attempt, UserStore, now_iso


E4, E5, NF3 = (
    chess.Move.from_uci("e2e4"),
    chess.Move.from_uci("e7e5"),
    chess.Move.from_uci("g1f3"),
)

LINE = Puzzle(
    title="line",
    initial_fen=chess.STARTING_FEN,
    moves=(E4, E5, NF3),
    comments=("intro", "centre [%cal Ge7e5]", "", "develop"),
)


class FakeRoot:
    def __init__(self) -> None:
        self.pending: dict[str, object] = {}
        self._counter = 0

    def after(self, _delay: int, callback) -> str:
        self._counter += 1
        after_id = f"after{self._counter}"
        self.pending[after_id] = callback
        return after_id

    def after_cancel(self, after_id: str) -> None:
        self.pending.pop(after_id, None)

    def fire(self) -> None:
        assert len(self.pending) == 1, "expected exactly one scheduled callback"
        _, callback = self.pending.popitem()
        callback()


class FakeBoardView:
    def __init__(self) -> None:
        self.moves: list[chess.Move | None] = []
        self.flashed: list[chess.Move] = []
        self.annotations = None

    def advance_position(self, board, move, *, animate: bool = True, **_kwargs) -> None:
        self.moves.append(move)

    def flash_move(self, move, *_args) -> None:
        self.flashed.append(move)

    def set_annotations(self, annotations) -> None:
        self.annotations = annotations


class FakeVar:
    def __init__(self, value=None) -> None:
        self.value = value

    def get(self):
        return self.value

    def set(self, value) -> None:
        self.value = value


class FakeAudio:
    def play_move(self, *_args) -> None:
        pass


class FakeLayout:
    def __init__(self) -> None:
        self.board = FakeBoardView()
        self.comment_view = object()


class FakeWindow:
    def __init__(self, session: PuzzleSession) -> None:
        self.session = session
        self.root = FakeRoot()
        self.audio = FakeAudio()
        self._layout = FakeLayout()
        self._status_var = FakeVar("")
        self._pause_for_comment_var = FakeVar(False)
        self._pause_playback_var = FakeVar(False)
        self.comment_text = ""
        self.resumed = False

    def _display_comment(self, comment: str) -> str:
        return comment

    def _replace_text(self, _widget, text: str) -> None:
        self.comment_text = text

    def _resume_after_lesson(self) -> None:
        self.resumed = True


def _lesson_setup() -> tuple[FakeWindow, RefutationPlayback]:
    session = PuzzleSession(LINE, chess.WHITE)
    window = FakeWindow(session)
    playback = RefutationPlayback(window)
    playback.start_lesson(list(LINE.moves), ["centre [%cal Ge7e5]", "", "develop"])
    return window, playback


def test_lesson_plays_all_moves_without_error_flash() -> None:
    window, playback = _lesson_setup()
    board_view = window._layout.board

    assert playback.is_lesson
    window.root.fire()
    window.root.fire()

    assert board_view.moves == [E4, E5, NF3]
    assert board_view.flashed == []  # a lesson is not a punished mistake
    assert board_view.annotations is not None  # author arrows shown
    assert window._status_var.value == "Line shown - press m, then play it yourself."
    assert not window.root.pending  # final position waits for the key


def test_lesson_rewinds_to_quiz_through_resume_hook() -> None:
    window, playback = _lesson_setup()
    window.root.fire()
    window.root.fire()

    assert playback.advance()  # continue key on the final position

    assert not playback.active
    assert window.resumed
    # Board rewound to the session position (the quiz point).
    assert window._layout.board.moves[-1] is None
    assert window.session.board.move_stack == []  # session never advanced


def test_empty_lesson_is_a_no_op() -> None:
    session = PuzzleSession(LINE, chess.WHITE)
    window = FakeWindow(session)
    playback = RefutationPlayback(window)

    playback.start_lesson([], [])

    assert not playback.active


class FakeDeck:
    def __init__(self, kind: str) -> None:
        self.kind = kind


class FakeUserStore:
    def __init__(self, known: set[str]) -> None:
        self.known = known

    def has_solved(self, puzzle_id: str) -> bool:
        return puzzle_id in self.known


class FakeDecisionWindow:
    """Just enough of MainWindow for _should_demonstrate (called unbound)."""

    def __init__(self, session, kind: str = "repertoire", known: set[str] | None = None) -> None:
        self.session = session
        self.database = FakeDeck(kind)
        self.user_store = FakeUserStore(known or set())
        self._demonstrate_var = FakeVar(True)
        self._line_demonstrated = False


def test_new_repertoire_line_is_demonstrated_once() -> None:
    session = PuzzleSession(LINE, chess.WHITE)
    window = FakeDecisionWindow(session)

    assert MainWindow._should_demonstrate(window)
    window._line_demonstrated = True
    assert not MainWindow._should_demonstrate(window)


def test_known_lines_and_tactics_decks_are_not_demonstrated() -> None:
    session = PuzzleSession(LINE, chess.WHITE)

    seen = FakeDecisionWindow(session, known={LINE.puzzle_id})
    assert not MainWindow._should_demonstrate(seen)

    tactics = FakeDecisionWindow(session, kind="tactics")
    assert not MainWindow._should_demonstrate(tactics)

    disabled = FakeDecisionWindow(session)
    disabled._demonstrate_var.set(False)
    assert not MainWindow._should_demonstrate(disabled)


def test_has_solved_counts_only_solves() -> None:
    store = UserStore.open(":memory:")
    try:
        assert not store.has_solved("abc")
        attempt = dict(
            puzzle_id="abc", at=now_iso(), mistakes=0, aids=0, duration_ms=1000, grade="good"
        )

        # Giving up is evidence of NOT knowing the line: still gets the lesson.
        store.record_attempt(Attempt(outcome="gave_up", **attempt))
        assert not store.has_solved("abc")

        store.record_attempt(Attempt(outcome="solved", **attempt))
        assert store.has_solved("abc")
        assert not store.has_solved("other")
    finally:
        store.close()
