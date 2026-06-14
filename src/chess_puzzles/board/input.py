from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import chess

from chess_puzzles.board.annotations import BoardAnnotations


class Modifier(str, Enum):
    SHIFT = "shift"
    CONTROL = "control"
    ALT = "alt"


@dataclass(frozen=True, slots=True)
class MoveRequested:
    move: chess.Move
    animate: bool = True


@dataclass(frozen=True, slots=True)
class SquareSelected:
    square: int | None


@dataclass(frozen=True, slots=True)
class AnnotationChanged:
    annotations: BoardAnnotations


@dataclass(frozen=True, slots=True)
class BoardFlipped:
    flipped: bool


BoardEvent = MoveRequested | SquareSelected | AnnotationChanged | BoardFlipped


SHIFT_MASK = 0x0001
CONTROL_MASK = 0x0004
ALT_MASKS = (0x0008, 0x0080)


def event_modifiers(state: int) -> frozenset[Modifier]:
    modifiers: set[Modifier] = set()
    if state & SHIFT_MASK:
        modifiers.add(Modifier.SHIFT)
    if state & CONTROL_MASK:
        modifiers.add(Modifier.CONTROL)
    if any(state & mask for mask in ALT_MASKS):
        modifiers.add(Modifier.ALT)
    return frozenset(modifiers)
