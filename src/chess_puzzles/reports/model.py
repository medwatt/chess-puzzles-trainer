from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AttemptSummary:
    attempted: int
    solved: int
    gave_up: int
    total_ms: int

    @property
    def avg_ms(self) -> int | None:
        return self.total_ms // self.attempted if self.attempted else None

    @property
    def solved_percent(self) -> int | None:
        return round(self.solved * 100 / self.attempted) if self.attempted else None
