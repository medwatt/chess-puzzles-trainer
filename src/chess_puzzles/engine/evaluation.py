from __future__ import annotations

from dataclasses import dataclass

import chess
import chess.engine

from chess_puzzles.constants import EVAL_BAR_CLAMP_CP, MATE_BAR_CP


@dataclass(frozen=True, slots=True)
class EngineScore:
    """Engine score stored from White's point of view."""

    white_cp: int
    mate: int | None = None

    @property
    def label(self) -> str:
        if self.mate is not None:
            sign = "" if self.mate > 0 else "-"
            return f"{sign}M{abs(self.mate)}"
        return f"{self.white_cp / 100:+.1f}"


def score_from_pov(score: chess.engine.PovScore) -> EngineScore | None:
    white_score = score.pov(chess.WHITE)
    mate = white_score.mate()
    if mate is not None:
        return EngineScore(white_cp=MATE_BAR_CP if mate > 0 else -MATE_BAR_CP, mate=mate)
    cp = white_score.score()
    if cp is None:
        return None
    return EngineScore(white_cp=cp)


def bar_white_fraction(score: EngineScore | None) -> float:
    if score is None:
        return 0.5
    cp = max(-EVAL_BAR_CLAMP_CP, min(EVAL_BAR_CLAMP_CP, score.white_cp))
    return 0.5 + (cp / (2 * EVAL_BAR_CLAMP_CP))
