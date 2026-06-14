from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import chess

from chess_puzzles.board.board_state import BoardRenderState
from chess_puzzles.board.canvas_backend import BoardRenderBackend
from chess_puzzles.board.control import ControlOverlayMode, contested_square_margins, squares_in_danger
from chess_puzzles.board.geometry import BoardGeometry
from chess_puzzles.board.images import BoardTextureCache, PieceImageCache
from chess_puzzles.board.render_geometry import (
    arrow_shape,
    coordinate_font_size,
    coordinate_labels,
    is_light_square,
    square_fill,
)
from chess_puzzles.board.render_plan import BoardChanges


class BoardLayer(Protocol):
    name: str
    z_index: int

    def attach(self, backend: BoardRenderBackend) -> None: ...

    def update(self, state: BoardRenderState, geometry: BoardGeometry, changes: BoardChanges) -> bool: ...

    def redraw(self, state: BoardRenderState, geometry: BoardGeometry) -> None: ...

    def clear(self) -> None: ...


@dataclass(slots=True)
class BaseLayer:
    name: str
    z_index: int
    backend: BoardRenderBackend | None = None

    def attach(self, backend: BoardRenderBackend) -> None:
        self.backend = backend

    def should_update(self, changes: BoardChanges) -> bool:
        return changes.all_changed

    def update(self, state: BoardRenderState, geometry: BoardGeometry, changes: BoardChanges) -> bool:
        if self.should_update(changes):
            self.redraw(state, geometry)
            return True
        return False

    def clear(self) -> None:
        assert self.backend is not None
        self.backend.clear_tag(self.name)

    def redraw(self, state: BoardRenderState, geometry: BoardGeometry) -> None:
        self.clear()


class BoardSquaresLayer(BaseLayer):
    def __init__(self) -> None:
        super().__init__("board_squares", 0)
        self._textures = BoardTextureCache()
        self._drawn_images: list[object] = []

    def redraw(self, state: BoardRenderState, geometry: BoardGeometry) -> None:
        assert self.backend is not None
        self.clear()
        self._drawn_images.clear()
        for square in chess.SQUARES:
            x1, y1, x2, y2 = geometry.square_pixel_region(square, state.flipped)
            is_light = is_light_square(square)
            fill = square_fill(state, square)
            texture_path = state.board_theme.texture_light if is_light else state.board_theme.texture_dark
            # No outline: a 1px outline would paint one pixel beyond the snapped
            # region, making the fill overhang overlays by a pixel. Snapped edges
            # already tile the fills with no gap, so the outline isn't needed.
            self.backend.rectangle(self.name, x1, y1, x2, y2, fill=fill, outline="")
            if texture_path is not None:
                image = self._textures.image_for(texture_path, int(round(geometry.square_size)))
                if image is not None:
                    self._drawn_images.append(image)
                    self.backend.image(self.name, (x1 + x2) / 2, (y1 + y2) / 2, image)


class CoordinatesLayer(BaseLayer):
    def __init__(self) -> None:
        super().__init__("coordinates", 55)

    def should_update(self, changes: BoardChanges) -> bool:
        return changes.all_changed or changes.coordinates_visibility_changed

    def redraw(self, state: BoardRenderState, geometry: BoardGeometry) -> None:
        assert self.backend is not None
        self.clear()
        if not state.show_coordinates:
            return
        font = ("TkDefaultFont", coordinate_font_size(geometry), "bold")
        for label in coordinate_labels(state, geometry):
            self.backend.text(
                self.name, label.x, label.y, text=label.text, fill=label.color, font=font, anchor=label.anchor
            )


class ControlOverlayLayer(BaseLayer):
    """Highlights hanging pieces or shows the square-control heatmap."""

    def __init__(self) -> None:
        super().__init__("control_overlay", 15)

    def should_update(self, changes: BoardChanges) -> bool:
        return changes.all_changed or changes.control_overlay_changed

    def redraw(self, state: BoardRenderState, geometry: BoardGeometry) -> None:
        assert self.backend is not None
        self.clear()
        if state.control_overlay is ControlOverlayMode.HANGING:
            for square in squares_in_danger(state.board):
                self._tint(state, geometry, square, state.annotation_theme.danger_color, "gray50")
        elif state.control_overlay is ControlOverlayMode.CONTROL:
            for square, margin in contested_square_margins(state.board).items():
                color = (
                    state.annotation_theme.control_white_color
                    if margin > 0
                    else state.annotation_theme.control_black_color
                )
                self._tint(state, geometry, square, color, _control_stipple(margin))

    def _tint(
        self,
        state: BoardRenderState,
        geometry: BoardGeometry,
        square: int,
        color: str,
        stipple: str,
    ) -> None:
        # Tk has no alpha channel, so a stippled fill looks weak on its
        # own. The solid border ring carries the colour and the fill
        # gives it some body. The marker is inset inside the square as a deliberate
        # margin around the piece.
        assert self.backend is not None
        x1, y1, x2, y2 = geometry.square_pixel_region(square, state.flipped)
        margin = geometry.square_size * 0.08
        border = max(2.0, geometry.square_size * 0.05)
        inset = margin + border / 2
        self.backend.rectangle(
            self.name,
            x1 + inset,
            y1 + inset,
            x2 - inset,
            y2 - inset,
            fill=color,
            outline=color,
            width=border,
            stipple=stipple,
        )


class SelectionLayer(BaseLayer):
    def __init__(self) -> None:
        super().__init__("selection", 20)

    def should_update(self, changes: BoardChanges) -> bool:
        return changes.all_changed or changes.selection_changed

    def redraw(self, state: BoardRenderState, geometry: BoardGeometry) -> None:
        assert self.backend is not None
        self.clear()
        if state.selected_square is not None:
            x1, y1, x2, y2 = geometry.square_pixel_region(state.selected_square, state.flipped)
            self.backend.rectangle(
                self.name,
                x1,
                y1,
                x2,
                y2,
                fill=state.board_theme.selected_square,
                outline="",
                stipple="gray50",
            )
        if state.capabilities.legal_move_hints:
            radius = geometry.square_size * 0.14
            for square in state.legal_targets:
                cx, cy = geometry.square_center(square, state.flipped)
                self.backend.oval(
                    self.name,
                    cx - radius,
                    cy - radius,
                    cx + radius,
                    cy + radius,
                    fill=state.board_theme.legal_target,
                    outline="",
                )


class AnnotationSquaresLayer(BaseLayer):
    def __init__(self) -> None:
        super().__init__("annotation_squares", 30)

    def should_update(self, changes: BoardChanges) -> bool:
        return changes.all_changed or changes.annotations_changed

    def redraw(self, state: BoardRenderState, geometry: BoardGeometry) -> None:
        assert self.backend is not None
        self.clear()
        if not state.capabilities.annotations:
            return
        # Even stroke width so the inset (half the width) lands on whole pixels and
        # the border's outer edge sits exactly on the square's snapped boundary.
        width = max(2, round(geometry.square_size * state.annotation_theme.square_stroke_scale / 2) * 2)
        half = width / 2
        for mark in state.annotations.squares:
            x1, y1, x2, y2 = geometry.square_pixel_region(mark.square, state.flipped)
            self.backend.rectangle(
                self.name,
                x1 + half,
                y1 + half,
                x2 - half,
                y2 - half,
                fill="",
                outline=state.annotation_theme.colors[mark.color],
                width=width,
            )


class AnnotationCirclesLayer(BaseLayer):
    def __init__(self) -> None:
        super().__init__("annotation_circles", 40)

    def should_update(self, changes: BoardChanges) -> bool:
        return changes.all_changed or changes.annotations_changed

    def redraw(self, state: BoardRenderState, geometry: BoardGeometry) -> None:
        assert self.backend is not None
        self.clear()
        if not state.capabilities.annotations:
            return
        width = max(2.0, geometry.square_size * state.annotation_theme.square_stroke_scale)
        radius = geometry.square_size * state.annotation_theme.circle_radius_scale
        for circle in state.annotations.circles:
            cx, cy = geometry.square_center(circle.square, state.flipped)
            self.backend.oval(
                self.name,
                cx - radius,
                cy - radius,
                cx + radius,
                cy + radius,
                fill="",
                outline=state.annotation_theme.colors[circle.color],
                width=width,
            )


class PiecesLayer(BaseLayer):
    def __init__(self) -> None:
        super().__init__("pieces", 50)
        self._images = PieceImageCache()
        self._drawn_images: list[object] = []

    def should_update(self, changes: BoardChanges) -> bool:
        # animation_squares_changed fires only when the move changes (start
        # or end), not on every tick: we hide the source/target squares from
        # the piece layer while a piece is animating. tick-only animation
        # does not need a full piece redraw.
        return changes.all_changed or changes.pieces_changed or changes.animation_squares_changed or changes.drag_origin_changed

    def redraw(self, state: BoardRenderState, geometry: BoardGeometry) -> None:
        assert self.backend is not None
        self.clear()
        self._drawn_images.clear()
        animated_from = state.animation.move.from_square if state.animation is not None else None
        animated_to = state.animation.move.to_square if state.animation is not None else None
        dragged_from = state.drag_piece.origin if state.drag_piece is not None else None
        for square, piece in state.board.piece_map().items():
            if square in {animated_from, animated_to, dragged_from}:
                continue
            cx, cy = geometry.square_center(square, state.flipped)
            _draw_piece(self.backend, self.name, state, geometry, piece, cx, cy, self._images, self._drawn_images)


class AnnotationArrowsLayer(BaseLayer):
    def __init__(self) -> None:
        super().__init__("annotation_arrows", 70)

    def should_update(self, changes: BoardChanges) -> bool:
        return changes.all_changed or changes.annotations_changed or changes.live_arrow_changed

    def redraw(self, state: BoardRenderState, geometry: BoardGeometry) -> None:
        assert self.backend is not None
        self.clear()
        if not state.capabilities.annotations:
            return
        for arrow in state.annotations.arrows:
            _draw_arrow(
                self.backend,
                self.name,
                geometry,
                state,
                arrow.origin,
                arrow.target,
                state.annotation_theme.colors[arrow.color],
                state.annotation_theme.arrow_stroke_scale,
            )
        if state.live_arrow is not None:
            origin, target = state.live_arrow
            _draw_arrow(
                self.backend,
                self.name,
                geometry,
                state,
                origin,
                target,
                state.annotation_theme.colors[state.live_arrow_color],
                state.annotation_theme.arrow_stroke_scale,
            )


class LastMoveLayer(BaseLayer):
    def __init__(self) -> None:
        super().__init__("last_move", 80)

    def should_update(self, changes: BoardChanges) -> bool:
        return changes.all_changed or changes.last_move_changed

    def redraw(self, state: BoardRenderState, geometry: BoardGeometry) -> None:
        assert self.backend is not None
        self.clear()
        if state.capabilities.last_move and state.last_move is not None:
            _draw_arrow(
                self.backend,
                self.name,
                geometry,
                state,
                state.last_move.from_square,
                state.last_move.to_square,
                state.annotation_theme.last_move_color,
                state.annotation_theme.last_move_stroke_scale,
            )


class ThreatLayer(BaseLayer):
    """One-shot arrow showing the opponent's threat in the current position."""

    def __init__(self) -> None:
        super().__init__("threat", 85)

    def should_update(self, changes: BoardChanges) -> bool:
        return changes.all_changed or changes.threat_changed

    def redraw(self, state: BoardRenderState, geometry: BoardGeometry) -> None:
        assert self.backend is not None
        self.clear()
        if state.threat_move is None:
            return
        _draw_arrow(
            self.backend,
            self.name,
            geometry,
            state,
            state.threat_move.from_square,
            state.threat_move.to_square,
            state.annotation_theme.threat_color,
            state.annotation_theme.arrow_stroke_scale,
        )


class FlashLayer(BaseLayer):
    def __init__(self) -> None:
        super().__init__("flash", 90)

    def should_update(self, changes: BoardChanges) -> bool:
        return changes.all_changed or changes.flash_changed

    def redraw(self, state: BoardRenderState, geometry: BoardGeometry) -> None:
        assert self.backend is not None
        self.clear()
        if state.flash is None:
            return
        for square in state.flash.squares:
            x1, y1, x2, y2 = geometry.square_pixel_region(square, state.flipped)
            self.backend.rectangle(
                self.name,
                x1,
                y1,
                x2,
                y2,
                fill=state.flash.color,
                outline="",
                stipple="gray50",
            )


class AnimationLayer(BaseLayer):
    def __init__(self) -> None:
        super().__init__("animation", 100)
        self._images = PieceImageCache()
        self._drawn_images: list[object] = []

    def should_update(self, changes: BoardChanges) -> bool:
        return changes.all_changed or changes.animation_changed

    def redraw(self, state: BoardRenderState, geometry: BoardGeometry) -> None:
        assert self.backend is not None
        self.clear()
        self._drawn_images.clear()
        animation = state.animation
        if animation is None:
            return
        start_file, start_rank = geometry.display_coords(animation.move.from_square, state.flipped)
        end_file, end_rank = geometry.display_coords(animation.move.to_square, state.flipped)
        progress = max(0.0, min(1.0, animation.progress))
        display_file = start_file + (end_file - start_file) * progress
        display_rank = start_rank + (end_rank - start_rank) * progress
        cx = geometry.left + (display_file + 0.5) * geometry.square_size
        cy = geometry.top + (display_rank + 0.5) * geometry.square_size
        _draw_piece(self.backend, self.name, state, geometry, animation.piece, cx, cy, self._images, self._drawn_images)


class DragPieceLayer(BaseLayer):
    def __init__(self) -> None:
        super().__init__("drag_piece", 110)
        self._images = PieceImageCache()
        self._drawn_images: list[object] = []

    def should_update(self, changes: BoardChanges) -> bool:
        return changes.all_changed or changes.drag_piece_changed

    def redraw(self, state: BoardRenderState, geometry: BoardGeometry) -> None:
        assert self.backend is not None
        self.clear()
        self._drawn_images.clear()
        drag_piece = state.drag_piece
        if drag_piece is None:
            return
        _draw_piece(
            self.backend,
            self.name,
            state,
            geometry,
            drag_piece.piece,
            drag_piece.x,
            drag_piece.y,
            self._images,
            self._drawn_images,
        )


def default_layers() -> list[BoardLayer]:
    return [
        BoardSquaresLayer(),
        ControlOverlayLayer(),
        CoordinatesLayer(),
        SelectionLayer(),
        AnnotationSquaresLayer(),
        AnnotationCirclesLayer(),
        PiecesLayer(),
        AnnotationArrowsLayer(),
        LastMoveLayer(),
        ThreatLayer(),
        FlashLayer(),
        AnimationLayer(),
        DragPieceLayer(),
    ]


def _control_stipple(margin: int) -> str:
    # Use Tk stipple density to show the strength of the contested square.
    magnitude = abs(margin)
    if magnitude == 1:
        return "gray25"
    if magnitude == 2:
        return "gray50"
    return "gray75"


def _draw_arrow(
    backend: BoardRenderBackend,
    tag: str,
    geometry: BoardGeometry,
    state: BoardRenderState,
    origin: int,
    target: int,
    color: str,
    width_scale: float,
) -> None:
    shape = arrow_shape(geometry, state.annotation_theme, origin, target, state.flipped, width_scale)
    if shape is None:
        return
    backend.line(
        tag,
        (*shape.shaft_start, *shape.shaft_end),
        fill=color,
        width=shape.width,
        capstyle="round",
    )
    backend.polygon(tag, shape.head, fill=color, outline=color)


def _draw_piece(
    backend: BoardRenderBackend,
    tag: str,
    state: BoardRenderState,
    geometry: BoardGeometry,
    piece: chess.Piece,
    cx: float,
    cy: float,
    images: PieceImageCache,
    drawn_images: list[object],
) -> None:
    if state.piece_theme.image_directory is None:
        return
    image = images.image_for(piece, state.piece_theme.image_directory, int(geometry.square_size * 0.95))
    if image is None:
        return
    drawn_images.append(image)
    backend.image(tag, cx, cy, image)
