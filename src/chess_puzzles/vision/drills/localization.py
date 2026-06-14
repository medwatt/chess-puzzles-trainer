"""Drill 1 -- square localization: a coordinate is named, click the square."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import ClassVar

import chess

from chess_puzzles.vision.drill import DrillKind, DrillOption, Question


@dataclass(frozen=True, slots=True)
class LocalizationDrill:
    id: ClassVar[str] = "localization"
    name: ClassVar[str] = "Square localization"
    kind: ClassVar[DrillKind] = DrillKind.SINGLE_CLICK
    # Coordinates would make this trivial, so the window keeps them hidden.
    show_coordinates: ClassVar[bool] = False
    OPTIONS: ClassVar[tuple[DrillOption, ...]] = (
        DrillOption("orientation", "View", (("White", chess.WHITE), ("Black", chess.BLACK))),
    )

    # A fixed perspective (not random) -- a random one could only be read off the
    # coordinates, which are hidden here.
    orientation: chess.Color = chess.WHITE

    def accepts(self, board: chess.Board) -> bool:
        return True

    def make_question(self, board: chess.Board, rng: random.Random) -> Question:
        # An empty board keeps the task to pure coordinate finding.
        square = rng.randrange(64)
        name = chess.square_name(square)
        return Question(
            fen=chess.Board(None).fen(),
            orientation=self.orientation,
            prompt=f"Click {name}",
            answer=frozenset({square}),
            label=name,
        )


drill = LocalizationDrill()
