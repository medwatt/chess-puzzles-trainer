from __future__ import annotations

from chess_puzzles.board.board_state import BoardRenderState
from chess_puzzles.board.canvas_backend import BoardRenderBackend
from chess_puzzles.board.geometry import BoardGeometry
from chess_puzzles.board.layers import BoardLayer, default_layers
from chess_puzzles.board.render_plan import BoardChanges, calculate_changes


class BoardRenderCoordinator:
    def __init__(
        self,
        backend: BoardRenderBackend,
        *,
        layers: list[BoardLayer] | None = None,
    ) -> None:
        self._backend = backend
        self._layers = sorted(layers or default_layers(), key=lambda layer: layer.z_index)
        self._last_state: BoardRenderState | None = None
        self._last_geometry: BoardGeometry | None = None
        for layer in self._layers:
            layer.attach(backend)

    @property
    def layers(self) -> tuple[BoardLayer, ...]:
        return tuple(self._layers)

    def render(self, state: BoardRenderState, geometry: BoardGeometry) -> BoardChanges:
        changes = calculate_changes(self._last_state, state, self._last_geometry, geometry)
        first_redrawn: int | None = None
        for index, layer in enumerate(self._layers):
            if layer.update(state, geometry, changes) and first_redrawn is None:
                first_redrawn = index
        # Canvas draws newer items on top. After a layer redraws (which
        # deletes and re-creates items), re-raise it and every layer
        # above it so the z-order stays correct.
        if first_redrawn is not None:
            for layer in self._layers[first_redrawn:]:
                self._backend.raise_tag(layer.name)
        self._last_state = state
        self._last_geometry = geometry
        return changes
