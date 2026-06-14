from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AnnotationColor(str, Enum):
    GREEN = "green"
    RED = "red"
    BLUE = "blue"
    YELLOW = "yellow"


@dataclass(frozen=True, slots=True)
class CircleAnnotation:
    square: int
    color: AnnotationColor = AnnotationColor.GREEN


@dataclass(frozen=True, slots=True)
class SquareAnnotation:
    square: int
    color: AnnotationColor = AnnotationColor.GREEN


@dataclass(frozen=True, slots=True)
class ArrowAnnotation:
    origin: int
    target: int
    color: AnnotationColor = AnnotationColor.GREEN


@dataclass(frozen=True, slots=True)
class BoardAnnotations:
    circles: tuple[CircleAnnotation, ...] = field(default_factory=tuple)
    squares: tuple[SquareAnnotation, ...] = field(default_factory=tuple)
    arrows: tuple[ArrowAnnotation, ...] = field(default_factory=tuple)

    @classmethod
    def empty(cls) -> "BoardAnnotations":
        return cls()

    def toggle_circle(
        self,
        square: int,
        color: AnnotationColor = AnnotationColor.GREEN,
    ) -> "BoardAnnotations":
        circle = CircleAnnotation(square=square, color=color)
        if circle in self.circles:
            circles = tuple(existing for existing in self.circles if existing != circle)
        else:
            circles = tuple(existing for existing in self.circles if existing.square != square)
            circles = (*circles, circle)
        return BoardAnnotations(circles=circles, squares=self.squares, arrows=self.arrows)

    def toggle_square(
        self,
        square: int,
        color: AnnotationColor = AnnotationColor.GREEN,
    ) -> "BoardAnnotations":
        mark = SquareAnnotation(square=square, color=color)
        if mark in self.squares:
            squares = tuple(existing for existing in self.squares if existing != mark)
        else:
            squares = tuple(existing for existing in self.squares if existing.square != square)
            squares = (*squares, mark)
        return BoardAnnotations(circles=self.circles, squares=squares, arrows=self.arrows)

    def toggle_arrow(
        self,
        origin: int,
        target: int,
        color: AnnotationColor = AnnotationColor.GREEN,
    ) -> "BoardAnnotations":
        arrow = ArrowAnnotation(origin=origin, target=target, color=color)
        if arrow in self.arrows:
            arrows = tuple(existing for existing in self.arrows if existing != arrow)
        else:
            arrows = tuple(
                existing
                for existing in self.arrows
                if existing.origin != origin or existing.target != target
            )
            arrows = (*arrows, arrow)
        return BoardAnnotations(circles=self.circles, squares=self.squares, arrows=arrows)
