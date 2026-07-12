"""Parse PGN comment text into display prose and board annotations.

PGN comments often contain embedded markup like [%csl Ra1,Gb2]
(colored squares) and [%cal Ge2e4] (colored arrows), along with
other [%...] commands such as clock readings. This module is the
one place that understands that syntax. It splits a raw comment
into clean prose and a BoardAnnotations object, so the PGN viewer,
comment sidebar, exports, and anything else that shows comments all
get the same result.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import chess

from chess_puzzles.board.annotations import (
    AnnotationColor,
    ArrowAnnotation,
    BoardAnnotations,
    CircleAnnotation,
)
from chess_puzzles.text_utils import clean_comment_text


# The leading letter of each csl/cal token picks the color.
ANNOTATION_COLORS = {
    "G": AnnotationColor.GREEN,
    "R": AnnotationColor.RED,
    "B": AnnotationColor.BLUE,
    "Y": AnnotationColor.YELLOW,
}

_CSL_RE = re.compile(r"\[%csl\s+([^\]]+)\]")
_CAL_RE = re.compile(r"\[%cal\s+([^\]]+)\]")
_COMMAND_RE = re.compile(r"[ \t]*\[%[^\]]*\][ \t]*")

# Course exporters (Chessable and friends) embed app directives in comments as
# @@StartName@@...@@EndName@@ spans. How a span renders as prose depends only
# on its name, so supporting another exporter means one entry here, not new
# parsing: FEN spans are diagram directives (the board already shows the
# position -- drop them), Bracket spans hold engine evaluations (keep, shown
# parenthesized as the source app renders them). Unknown spans keep their text,
# losing only the markers.
_MARKER_SPAN_RE = re.compile(r"@@Start(\w+)@@(.*?)@@End\1@@", re.DOTALL)
_MARKER_STRAY_RE = re.compile(r"[ \t]*@@\w+@@[ \t]*")
_MARKER_SPAN_RENDERERS = {
    "FEN": lambda text: "",
    "Bracket": lambda text: f"({text.strip()})",
}


def _replace_marker_span(match: re.Match[str]) -> str:
    renderer = _MARKER_SPAN_RENDERERS.get(match.group(1), lambda text: text.strip())
    return renderer(match.group(2))


@dataclass(frozen=True, slots=True)
class ParsedComment:
    """One PGN comment, split into prose and annotations.

    prose has every [%...] command removed and whitespace normalized
    while keeping paragraph breaks. annotations holds the circles and
    arrows the comment asked for.
    """

    prose: str
    annotations: BoardAnnotations

    @property
    def inline_prose(self) -> str:
        """The prose collapsed to a single line, for narrow display contexts."""
        return " ".join(self.prose.split())


def parse_comment(comment: str) -> ParsedComment:
    return ParsedComment(
        prose=clean_comment_text(strip_annotation_commands(comment)),
        annotations=annotations_from_comment(comment),
    )


def strip_annotation_commands(comment: str) -> str:
    """Remove every [%...] command and @@...@@ exporter marker from the text."""
    text = _MARKER_SPAN_RE.sub(_replace_marker_span, comment)
    text = _MARKER_STRAY_RE.sub(" ", text)
    return _COMMAND_RE.sub(" ", text).strip()


def annotations_from_comment(comment: str) -> BoardAnnotations:
    """Convert [%csl]/[%cal] commands into board circles and arrows."""
    circles: list[CircleAnnotation] = []
    for match in _CSL_RE.finditer(comment):
        for token in match.group(1).split(","):
            token = token.strip()
            if len(token) < 3:
                continue
            try:
                square = chess.parse_square(token[1:3].lower())
            except ValueError:
                continue
            circles.append(CircleAnnotation(square, _annotation_color(token[0])))
    arrows: list[ArrowAnnotation] = []
    for match in _CAL_RE.finditer(comment):
        for token in match.group(1).split(","):
            token = token.strip()
            if len(token) < 5:
                continue
            try:
                origin = chess.parse_square(token[1:3].lower())
                target = chess.parse_square(token[3:5].lower())
            except ValueError:
                continue
            arrows.append(ArrowAnnotation(origin, target, _annotation_color(token[0])))
    return BoardAnnotations(circles=tuple(circles), arrows=tuple(arrows))


def _annotation_color(letter: str) -> AnnotationColor:
    return ANNOTATION_COLORS.get(letter.upper(), AnnotationColor.GREEN)
