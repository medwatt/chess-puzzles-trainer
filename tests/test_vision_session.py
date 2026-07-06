from __future__ import annotations

import dataclasses
import random

import chess
import pytest

from chess_puzzles.vision.drill import DrillKind, Question, TrialResult
from chess_puzzles.vision.registry import registry
from chess_puzzles.vision.session import VisionSession
from chess_puzzles.vision.source import ListPositionSource, PositionUnavailable


class _FixedClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _session(drill_id: str, fens: tuple[str, ...], clock: _FixedClock) -> VisionSession:
    return VisionSession(
        registry.get(drill_id),
        ListPositionSource(fens),
        rng=random.Random(0),
        clock=clock,
    )


def test_trialresult_grade_partitions_squares() -> None:
    result = TrialResult.grade(frozenset({1, 2, 3}), frozenset({2, 3, 9}), 1000)
    assert result.correct == frozenset({2, 3})
    assert result.missed == frozenset({1})
    assert result.wrong == frozenset({9})
    assert result.passed is False


def test_multi_click_toggle_and_exact_match() -> None:
    clock = _FixedClock()
    session = _session("reach-knight", ("4k3/8/8/8/3N4/8/8/4K3 w - - 0 1",), clock)
    question = session.next_question()
    for square in question.answer:
        session.toggle(square)
    session.toggle(chess.A1)  # extra wrong click
    session.toggle(chess.A1)  # toggled back off
    clock.now = 3.5
    result = session.submit()
    assert result.passed is True
    assert result.elapsed_ms == 3500
    assert session.stats.trials == 1 and session.stats.passed == 1


def test_single_click_keeps_only_latest() -> None:
    session = _session("localization", ("4k3/8/8/8/8/8/8/4K3 w - - 0 1",), _FixedClock())
    assert session.is_single_click
    session.next_question()
    session.toggle(chess.A1)
    session.toggle(chess.B2)
    assert session.clicks == frozenset({chess.B2})


def test_accuracy_and_average_accumulate() -> None:
    clock = _FixedClock()
    session = _session("reach-knight", ("4k3/8/8/8/3N4/8/8/4K3 w - - 0 1",), clock)
    session.next_question()
    clock.now = 2.0
    session.submit()  # zero clicks -> fail
    session.next_question()
    for square in session.question.answer:
        session.toggle(square)
    clock.now = 4.0
    session.submit()  # pass
    assert session.stats.trials == 2 and session.stats.passed == 1
    assert session.stats.accuracy == 50.0
    assert session.stats.average_ms == 2000  # (2000 + 2000) / 2


def test_streak_grows_on_pass_and_resets_on_miss() -> None:
    session = _session("reach-knight", ("4k3/8/8/8/3N4/8/8/4K3 w - - 0 1",), _FixedClock())
    session.next_question()
    for square in session.question.answer:
        session.toggle(square)
    session.submit()  # pass
    assert session.stats.streak == 1
    session.next_question()
    session.submit()  # zero clicks -> miss
    assert session.stats.streak == 0
    session.next_question()
    for square in session.question.answer:
        session.toggle(square)
    session.submit()  # pass again
    assert session.stats.streak == 1


def test_source_without_match_raises() -> None:
    # Hanging drill over a position with nothing hanging.
    session = _session("hanging", ("4k3/8/8/8/8/8/8/4K3 w - - 0 1",), _FixedClock())
    with pytest.raises(PositionUnavailable):
        session.next_question()


# Nothing hanging (start position) vs a lone hanging black rook on d5.
_CLEAN_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
_HANGING_FEN = "4k3/8/8/3r4/8/8/8/3RK3 w - - 0 1"


def test_hanging_default_draws_only_positive_positions() -> None:
    drill = registry.get("hanging")
    assert getattr(drill, "negative_rate", 0.0) == 0.0
    session = VisionSession(drill, ListPositionSource((_CLEAN_FEN, _HANGING_FEN)), rng=random.Random(0))
    question = session.next_question()
    assert question.answer  # positive-only: never the clean board


def test_hanging_negative_trial_poses_an_empty_answer() -> None:
    drill = dataclasses.replace(registry.get("hanging"), negative_rate=1.0)
    session = VisionSession(drill, ListPositionSource((_CLEAN_FEN, _HANGING_FEN)), rng=random.Random(0))
    question = session.next_question()
    assert question.answer == frozenset()  # only the clean board qualifies
    result = session.submit()  # zero clicks exactly matches the empty answer
    assert result.passed is True and session.stats.passed == 1


# Nothing loose (black Bf8 defended by its king, unattacked) vs a lone loose
# black knight on d5 (attacked by Bg2, defended by the c6 pawn). Scope=opponent.
_NO_LOOSE_FEN = "4kb2/8/8/8/8/8/8/4K3 w - - 0 1"
_LOOSE_FEN = "4k3/8/2p5/3n4/8/8/6B1/4K3 w - - 0 1"


def test_loose_default_draws_only_positive_positions() -> None:
    drill = registry.get("loose")
    assert getattr(drill, "negative_rate", 0.0) == 0.0
    session = VisionSession(drill, ListPositionSource((_NO_LOOSE_FEN, _LOOSE_FEN)), rng=random.Random(0))
    question = session.next_question()
    assert question.answer  # positive-only: never the calm board


def test_loose_negative_trial_poses_an_empty_answer() -> None:
    drill = dataclasses.replace(registry.get("loose"), negative_rate=1.0)
    session = VisionSession(drill, ListPositionSource((_NO_LOOSE_FEN, _LOOSE_FEN)), rng=random.Random(0))
    question = session.next_question()
    assert question.answer == frozenset()  # only the calm board qualifies
    result = session.submit()  # zero clicks exactly matches the empty answer
    assert result.passed is True and session.stats.passed == 1


# White to move is in check (Black queen on a1 rakes the first rank at e1). The
# in-check pressure rule zeroes every attacker count, so the loose drill would
# otherwise serve a8/c8/a1 as 0-vs-0 "loose" pieces -- confusing nonsense.
_IN_CHECK_FEN = "rnb2Q2/3p1N1k/1p4p1/2ppP2p/7P/1P4P1/P4P2/q3K1NR w - - 0 1"


def test_in_check_positions_are_never_served() -> None:
    session = _session("loose", (_IN_CHECK_FEN,), _FixedClock())
    with pytest.raises(PositionUnavailable):
        session.next_question()


def test_captures_is_registered_after_checks() -> None:
    ids = registry.ids()
    assert ids[ids.index("checks") + 1] == "captures"


def test_captures_negative_trial_poses_an_empty_answer() -> None:
    drill = dataclasses.replace(registry.get("captures"), negative_rate=1.0)
    session = VisionSession(
        drill,
        ListPositionSource(
            (
                "4k3/8/8/8/8/8/8/4K3 w - - 0 1",
                "4k3/8/8/3n4/8/8/3R4/4K3 w - - 0 1",
            )
        ),
        rng=random.Random(0),
    )
    question = session.next_question()
    assert question.answer == frozenset()


def test_every_registered_drill_makes_a_question() -> None:
    board = "r1bqk2r/pppp1ppp/2n2n2/2b1p3/2B1P3/3P1N2/PPP2PPP/RNBQK2R w KQkq - 0 1"
    rng = random.Random(0)
    for drill in registry.all():
        chess_board = chess.Board(board)
        if not drill.accepts(chess_board):
            continue
        question = drill.make_question(chess_board, rng)
        assert isinstance(question, Question)
        assert question.prompt
        assert drill.kind in (DrillKind.SINGLE_CLICK, DrillKind.MULTI_CLICK)


def test_long_range_question_carries_feedback_arrows() -> None:
    # White rook d1 attacks the distant knight d5; the arrow explains the answer.
    board = chess.Board("4k3/8/8/3n4/8/8/8/3RK3 w - - 0 1")
    drill = registry.get("long-range")
    assert drill is not None and drill.accepts(board)
    question = drill.make_question(board, random.Random(0))
    assert question.answer == frozenset({chess.D1})
    assert question.feedback_arrows == frozenset({(chess.D1, chess.D5)})
    # Every arrow starts on an answer square, so the window can render blindly.
    assert {origin for origin, _ in question.feedback_arrows} <= question.answer
