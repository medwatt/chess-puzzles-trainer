from __future__ import annotations

import chess

from chess_puzzles.app.main_window import MainWindow
from chess_puzzles.puzzle import MoveResult, Puzzle, PuzzleSession
from chess_puzzles.puzzle.prefix import drill_prefix_length


GAME_PGN = """[Event "Course"]
[Result "*"]

1. e4 e5 2. Nf3 (2. f4 exf4 3. Nf3) 2... Nc6 3. Bb5 *
"""

E4, E5 = chess.Move.from_uci("e2e4"), chess.Move.from_uci("e7e5")
NF3, NC6, BB5 = (
    chess.Move.from_uci("g1f3"),
    chess.Move.from_uci("b8c6"),
    chess.Move.from_uci("f1b5"),
)
F4, EXF4 = chess.Move.from_uci("f2f4"), chess.Move.from_uci("e5f4")


def _line(moves: tuple[chess.Move, ...], pgn: str = GAME_PGN) -> Puzzle:
    return Puzzle(title="line", initial_fen=chess.STARTING_FEN, moves=moves, pgn_text=pgn)


LINE_ONE = _line((E4, E5, NF3, NC6, BB5))
LINE_TWO = _line((E4, E5, F4, EXF4, NF3))


def test_prefix_is_shared_move_count_within_same_game() -> None:
    assert drill_prefix_length(LINE_ONE, LINE_TWO) == 2


def test_first_line_has_no_prefix() -> None:
    assert drill_prefix_length(None, LINE_ONE) == 0


def test_cross_game_neighbors_share_their_common_moves() -> None:
    # Line-per-game exports (one PGN game per line) still share a trunk with
    # the previous line; the recap applies to whatever moves they have in common.
    other_game = _line((E4, E5, NF3), pgn='[Event "Other"]\n\n1. e4 e5 2. Nf3 *')
    assert drill_prefix_length(other_game, LINE_ONE) == 3


def test_different_start_positions_have_no_prefix() -> None:
    study = Puzzle(
        title="page",
        initial_fen="rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
        moves=(E5,),
        pgn_text=GAME_PGN,
    )
    assert drill_prefix_length(study, LINE_ONE) == 0


def test_identical_lines_drill_fully() -> None:
    assert drill_prefix_length(LINE_ONE, LINE_ONE) == 0


def test_session_recaps_prefix_then_takes_user_moves() -> None:
    session = PuzzleSession(LINE_TWO, chess.WHITE, prefix_length=2)

    # User input during the recap is not graded.
    assert session.in_prefix
    assert session.play_user_move(E4) is MoveResult.WAITING
    assert session.mistakes == 0

    # Both sides' moves auto-play through the prefix, no matter whose turn.
    assert session.play_prefix_move() == E4
    assert session.in_prefix
    assert session.play_prefix_move() == E5
    assert not session.in_prefix
    assert session.play_prefix_move() is None

    # Normal solving resumes at the divergence point.
    assert session.play_user_move(F4) is MoveResult.CORRECT
    assert session.play_computer_move() == EXF4
    assert session.play_user_move(NF3) is MoveResult.COMPLETE


def test_session_reset_restores_prefix() -> None:
    session = PuzzleSession(LINE_TWO, chess.WHITE, prefix_length=2)
    session.play_prefix_move()
    session.play_prefix_move()
    session.reset()

    assert session.in_prefix


class _FakeRoot:
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


class _FakeAudio:
    def play_move(self, *_args) -> None:
        pass


class _FakeRecapWindow:
    """Just enough of MainWindow for _play_prefix_step (called unbound)."""

    def __init__(self, session: PuzzleSession) -> None:
        self.session = session
        self.root = _FakeRoot()
        self.audio = _FakeAudio()
        self._prefix_after_id: str | None = None
        self.refreshed: list[tuple[str, chess.Move | None]] = []
        self.scheduled_reply = False
        self.solve_clock_started = False

    demonstrate = False

    def _play_prefix_step(self) -> None:
        MainWindow._play_prefix_step(self)

    def _refresh_from_session(self, status: str, move=None, **_kwargs) -> None:
        self.refreshed.append((status, move))

    def _should_demonstrate(self) -> bool:
        return self.demonstrate

    def _start_line_demonstration(self) -> None:
        self.demonstrated = True

    def _schedule_computer_reply(self) -> None:
        self.scheduled_reply = True

    def _maybe_start_solve_clock(self) -> None:
        self.solve_clock_started = True


def test_recap_chain_plays_prefix_and_hands_over() -> None:
    session = PuzzleSession(LINE_TWO, chess.WHITE, prefix_length=2)
    window = _FakeRecapWindow(session)

    MainWindow._play_prefix_step(window)  # plays e4, schedules next step
    assert session.board.move_stack == [E4]
    window.root.fire()  # plays e5 -> divergence reached

    assert session.board.move_stack == [E4, E5]
    assert not session.in_prefix
    # White (the player) is to move at the divergence: hand over, start clock.
    assert window.solve_clock_started
    assert not window.scheduled_reply
    assert window.refreshed[-1][0] == "The line continues here - your move."
    assert not window.root.pending


def test_recap_chain_schedules_reply_when_opponent_moves_at_divergence() -> None:
    # White repertoire whose prefix ends on White's own 2. Nf3: at the
    # divergence it is Black's (the opponent's) turn, so the normal
    # computer-reply flow takes over instead of the solve clock.
    line = _line((E4, E5, NF3, NC6, BB5))
    session = PuzzleSession(line, chess.WHITE, prefix_length=3)
    window = _FakeRecapWindow(session)

    MainWindow._play_prefix_step(window)
    window.root.fire()
    window.root.fire()

    assert session.board.move_stack == [E4, E5, NF3]
    assert not session.in_prefix
    assert window.scheduled_reply
    assert not window.solve_clock_started
    assert window.refreshed[-1][0] == "Recap done."


def test_recap_hands_over_to_demonstration_for_new_lines() -> None:
    session = PuzzleSession(LINE_TWO, chess.WHITE, prefix_length=2)
    window = _FakeRecapWindow(session)
    window.demonstrate = True

    MainWindow._play_prefix_step(window)
    window.root.fire()

    assert not session.in_prefix
    # The lesson starts one step later, so its first move (sound and
    # animation) does not land on top of the recap move that just played.
    assert not getattr(window, "demonstrated", False)
    window.root.fire()
    assert getattr(window, "demonstrated", False)
    assert not window.scheduled_reply
    assert not window.solve_clock_started
