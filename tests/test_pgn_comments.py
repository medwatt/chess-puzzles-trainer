from __future__ import annotations

import chess

from chess_puzzles.board.annotations import AnnotationColor
from chess_puzzles.pgn.comments import (
    annotations_from_comment,
    parse_comment,
    strip_annotation_commands,
)


def test_csl_and_cal_commands_become_board_annotations() -> None:
    comment = "Look here [%csl Rb3,Ga6] and follow [%cal Ga5e1,Yb7c5]"

    annotations = annotations_from_comment(comment)

    assert {(circle.square, circle.color) for circle in annotations.circles} == {
        (chess.B3, AnnotationColor.RED),
        (chess.A6, AnnotationColor.GREEN),
    }
    assert {(arrow.origin, arrow.target, arrow.color) for arrow in annotations.arrows} == {
        (chess.A5, chess.E1, AnnotationColor.GREEN),
        (chess.B7, chess.C5, AnnotationColor.YELLOW),
    }


def test_malformed_annotation_tokens_are_skipped() -> None:
    annotations = annotations_from_comment("[%csl Rz9,X,Gb2][%cal Gz1z2]")

    assert {(circle.square, circle.color) for circle in annotations.circles} == {(chess.B2, AnnotationColor.GREEN)}
    assert annotations.arrows == ()


def test_strip_annotation_commands_keeps_prose() -> None:
    assert strip_annotation_commands("[%csl Rb3] go to [b7] now [%clk 0:01:00]") == "go to [b7] now"


def test_parse_comment_splits_prose_and_annotations() -> None:
    comment = "[%csl Rb3] Consider the  \n    knight on [b7].\n\nIt forks  pieces."

    parsed = parse_comment(comment)

    assert parsed.prose == "Consider the knight on [b7].\n\nIt forks pieces."
    assert parsed.inline_prose == "Consider the knight on [b7]. It forks pieces."
    assert len(parsed.annotations.circles) == 1
