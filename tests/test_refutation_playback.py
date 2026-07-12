from __future__ import annotations

import chess

from chess_puzzles.app.refutation_playback import RefutationPlayback
from chess_puzzles.puzzle import MoveResult, Puzzle, PuzzleSession


TREE_PGN = """[Event "Tree"]
[Result "*"]

1. e4 {main} ( 1. f3 $4 {weakens [%cal Re8h5]} 1... e5 2. g4 $4 Qh4# {mate} )
1... e5 *
"""


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
        self.positions: list[str] = []
        self.moves: list[chess.Move | None] = []
        self.animate_flags: list[bool] = []
        self.annotations = None

    def advance_position(self, board, move, *, animate: bool = True, **_kwargs) -> None:
        self.positions.append(board.fen())
        self.moves.append(move)
        self.animate_flags.append(animate)

    def flash_move(self, move, *_args) -> None:
        self.flashed = getattr(self, "flashed", [])
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
    def __init__(self, session: PuzzleSession, pause_for_comment: bool, pause_playback: bool = False) -> None:
        self.session = session
        self.root = FakeRoot()
        self.audio = FakeAudio()
        self._layout = FakeLayout()
        self._status_var = FakeVar("")
        self._pause_for_comment_var = FakeVar(pause_for_comment)
        self._pause_playback_var = FakeVar(pause_playback)
        self.comment_text = ""

    def _display_comment(self, comment: str) -> str:
        return comment

    def _replace_text(self, _widget, text: str) -> None:
        self.comment_text = text


def _blundered_session() -> PuzzleSession:
    puzzle = Puzzle(
        title="Tree",
        initial_fen=chess.STARTING_FEN,
        moves=(chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")),
        comments=("find the best move", "", ""),
        pgn_text=TREE_PGN,
    )
    session = PuzzleSession(puzzle, chess.WHITE)
    assert session.play_user_move(chess.Move.from_uci("f2f3")) is MoveResult.BLUNDER
    return session


def test_playback_pauses_on_prose_and_rewinds_to_decision_point() -> None:
    session = _blundered_session()
    window = FakeWindow(session, pause_for_comment=True)
    playback = RefutationPlayback(window)

    playback.start(session.last_refutation)
    # The annotated blunder move plays immediately and waits for the key.
    assert playback.active
    board_view = window._layout.board
    assert board_view.moves == [chess.Move.from_uci("f2f3")]
    assert "weakens" in window.comment_text
    assert board_view.annotations is not None  # %cal arrow applied
    assert window.root.pending == {}  # paused: prose comment + pause setting

    assert playback.advance()  # continue key: 1...e5, silent -> timer runs
    window.root.fire()  # 2. g4, silent -> timer
    window.root.fire()  # 2...Qh4#, final step
    assert [m.uci() for m in board_view.moves] == ["f2f3", "e7e5", "g2g4", "d8h4"]
    assert "mate" in window.comment_text
    assert "try again" in window._status_var.value
    assert window.root.pending == {}  # final position always waits

    assert playback.advance()  # continue key from the end: rewind
    assert not playback.active
    assert board_view.positions[-1] == chess.Board(chess.STARTING_FEN).fen()
    assert board_view.moves[-1] is None
    assert window.comment_text == "find the best move"
    # The session never moved: the mistake is counted, the puzzle still open.
    assert session.mistakes == 1
    assert session.expected_move == chess.Move.from_uci("e2e4")


def test_dragged_blunder_does_not_reanimate_but_replies_do() -> None:
    session = _blundered_session()
    window = FakeWindow(session, pause_for_comment=False)
    playback = RefutationPlayback(window)

    # A dragged move arrives with animate=False, same as the correct-move path.
    playback.start(session.last_refutation, animate_first=False)
    window.root.fire()
    window.root.fire()
    window.root.fire()
    assert window._layout.board.animate_flags == [False, True, True, True]
    # Only the user's own move flashes (red); replies never flash.
    assert window._layout.board.flashed == [chess.Move.from_uci("f2f3")]


def test_playback_autoplays_when_pause_for_comment_is_off() -> None:
    session = _blundered_session()
    window = FakeWindow(session, pause_for_comment=False)
    playback = RefutationPlayback(window)

    playback.start(session.last_refutation)
    window.root.fire()
    window.root.fire()
    window.root.fire()
    assert len(window._layout.board.moves) == 4
    assert window.root.pending == {}  # final position still waits for the key


def test_coda_playback_rewinds_to_origin_then_returns_to_session_board() -> None:
    # Solve the puzzle first: the trap at the root was walked past.
    puzzle_session = _blundered_session()
    puzzle_session.reset()
    puzzle_session.play_user_move(chess.Move.from_uci("e2e4"))
    puzzle_session.play_computer_move()
    assert puzzle_session.is_complete

    window = FakeWindow(puzzle_session, pause_for_comment=False)
    playback = RefutationPlayback(window)
    (origin_fen, refutation), = puzzle_session.avoided_refutations()

    playback.start(refutation, origin=chess.Board(origin_fen))
    board_view = window._layout.board
    # First draw is the decision point itself (no move), then the trap plays.
    assert board_view.moves[0] is None
    assert board_view.positions[0] == origin_fen
    assert board_view.moves[1] == chess.Move.from_uci("f2f3")

    window.root.fire()
    window.root.fire()
    window.root.fire()
    assert playback.advance()  # from the final position: return
    # ... to the *session* board (the solved position), not the origin.
    assert board_view.positions[-1] == puzzle_session.board.fen()
    assert "complete" in window._status_var.value.lower()
    assert not playback.active


def test_pause_playback_setting_waits_on_every_move() -> None:
    session = _blundered_session()
    window = FakeWindow(session, pause_for_comment=False, pause_playback=True)
    playback = RefutationPlayback(window)

    playback.start(session.last_refutation)
    # Even silent moves wait for the continue key: no timers, ever.
    for expected_moves in (1, 2, 3):
        assert len(window._layout.board.moves) == expected_moves
        assert window.root.pending == {}
        assert playback.advance()
    assert len(window._layout.board.moves) == 4  # final position, waiting
    assert playback.advance()  # rewind
    assert not playback.active


def test_cancel_stops_timers_and_deactivates() -> None:
    session = _blundered_session()
    window = FakeWindow(session, pause_for_comment=False)
    playback = RefutationPlayback(window)

    playback.start(session.last_refutation)
    assert window.root.pending
    playback.cancel()
    assert not playback.active
    assert window.root.pending == {}
    assert not playback.advance()  # inactive playback does not consume the key
