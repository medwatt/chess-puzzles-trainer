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


def test_fen_marker_spans_are_dropped() -> None:
    comment = "The start @@StartFEN@@rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1@@EndFEN@@ position."

    assert strip_annotation_commands(comment) == "The start  position."


def test_bracket_marker_spans_render_parenthesized() -> None:
    comment = "King is in trouble @@StartBracket@@+7.0@@EndBracket@@. Keep attacking."

    assert strip_annotation_commands(comment) == "King is in trouble (+7.0). Keep attacking."


def test_unknown_marker_spans_keep_their_text() -> None:
    assert strip_annotation_commands("see @@StartNote@@ the plan @@EndNote@@ here") == "see the plan here"


def test_stray_markers_are_removed() -> None:
    assert strip_annotation_commands("before @@Diagram@@ after") == "before after"


def test_markers_and_commands_combine() -> None:
    comment = "eval @@StartBracket@@+2.0@@EndBracket@@ [%cal Ge2e4] push"

    assert strip_annotation_commands(comment) == "eval (+2.0) push"
