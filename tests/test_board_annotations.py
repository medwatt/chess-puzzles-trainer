from __future__ import annotations

import chess

from chess_puzzles.board.annotations import AnnotationColor, BoardAnnotations


def test_toggle_circle_replaces_color_and_toggles_same_mark_off() -> None:
    annotations = BoardAnnotations.empty()

    annotations = annotations.toggle_circle(chess.E4)
    assert len(annotations.circles) == 1

    annotations = annotations.toggle_circle(chess.E4, AnnotationColor.RED)
    assert len(annotations.circles) == 1
    assert annotations.circles[0].color == AnnotationColor.RED

    annotations = annotations.toggle_circle(chess.E4, AnnotationColor.RED)
    assert annotations.circles == ()


def test_toggle_arrow_uses_one_arrow_per_origin_target() -> None:
    annotations = BoardAnnotations.empty()

    annotations = annotations.toggle_arrow(chess.E2, chess.E4)
    annotations = annotations.toggle_arrow(chess.E2, chess.E4, AnnotationColor.BLUE)

    assert len(annotations.arrows) == 1
    assert annotations.arrows[0].color == AnnotationColor.BLUE
