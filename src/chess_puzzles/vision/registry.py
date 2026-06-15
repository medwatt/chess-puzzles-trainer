"""Registry of available drills, keyed by id.

The UI drill selector and the persisted ``last_drill_id`` both read from here.
To add a drill: create a module in ``drills/`` exposing a ``drill`` (or ``drills``)
object and add it to the registration list at the bottom -- nothing else changes.
"""

from __future__ import annotations

from chess_puzzles.vision.drill import Drill
from chess_puzzles.vision.drills import (
    attackers,
    captures,
    checks,
    hanging,
    king_zone,
    localization,
    long_range,
    reach,
    undefended,
)


class DrillRegistry:
    def __init__(self) -> None:
        self._drills: dict[str, Drill] = {}

    def register(self, drill: Drill) -> Drill:
        if drill.id in self._drills:
            raise ValueError(f"Duplicate drill id: {drill.id}")
        self._drills[drill.id] = drill
        return drill

    def get(self, drill_id: str) -> Drill | None:
        return self._drills.get(drill_id)

    def all(self) -> list[Drill]:
        return list(self._drills.values())

    def ids(self) -> list[str]:
        return list(self._drills)


# The single shared registry, populated with the built-in drills. Importing this
# module is enough for any consumer to see them. Registration order is the order
# of the drill drop-down: roughly most to least important for tactical vision --
# forcing-move scans first, then loose-piece/king vision, then piece geometry, with
# plain coordinate finding (the warm-up) last.
registry = DrillRegistry()
for _drill in (
    checks.drill,
    captures.drill,
    undefended.drill,
    hanging.drill,
    attackers.drill,
    long_range.drill,
    king_zone.drill,
    *reach.drills,
    localization.drill,
):
    registry.register(_drill)
