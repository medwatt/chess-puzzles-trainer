from __future__ import annotations

from dataclasses import dataclass

from chess_puzzles.board.board_state import BoardRenderState
from chess_puzzles.board.geometry import BoardGeometry


@dataclass(frozen=True, slots=True)
class BoardChanges:
    position_changed: bool = False
    pieces_changed: bool = False
    orientation_changed: bool = False
    geometry_changed: bool = False
    theme_changed: bool = False
    annotations_changed: bool = False
    selected_square_changed: bool = False
    legal_targets_changed: bool = False
    last_move_changed: bool = False
    flash_changed: bool = False
    animation_changed: bool = False
    animation_squares_changed: bool = False
    drag_piece_changed: bool = False
    drag_origin_changed: bool = False
    live_arrow_changed: bool = False
    coordinates_visibility_changed: bool = False
    threat_changed: bool = False
    control_overlay_changed: bool = False

    @property
    def all_changed(self) -> bool:
        return self.position_changed or self.orientation_changed or self.geometry_changed or self.theme_changed

    @property
    def selection_changed(self) -> bool:
        return self.selected_square_changed or self.legal_targets_changed


def calculate_changes(
    old_state: BoardRenderState | None,
    new_state: BoardRenderState,
    old_geometry: BoardGeometry | None,
    new_geometry: BoardGeometry,
) -> BoardChanges:
    if old_state is None or old_geometry is None:
        return BoardChanges(
            position_changed=True,
            pieces_changed=True,
            orientation_changed=True,
            geometry_changed=True,
            theme_changed=True,
            annotations_changed=True,
            selected_square_changed=True,
            legal_targets_changed=True,
            last_move_changed=True,
            flash_changed=True,
            animation_changed=True,
            animation_squares_changed=True,
            drag_piece_changed=True,
            drag_origin_changed=True,
            live_arrow_changed=True,
            coordinates_visibility_changed=True,
            threat_changed=True,
            control_overlay_changed=True,
        )

    # copy_with() copies the Board object whenever the position changes.
    # If it is the same object, the position hasn't changed, so we can
    # skip the expensive FEN-string comparison on every animation tick
    # and drag frame.
    position_changed = old_state.board is not new_state.board and old_state.board.board_fen() != new_state.board.board_fen()
    old_drag_origin = old_state.drag_piece.origin if old_state.drag_piece is not None else None
    new_drag_origin = new_state.drag_piece.origin if new_state.drag_piece is not None else None
    old_animation_move = old_state.animation.move if old_state.animation is not None else None
    new_animation_move = new_state.animation.move if new_state.animation is not None else None
    return BoardChanges(
        position_changed=position_changed,
        pieces_changed=position_changed,
        orientation_changed=old_state.flipped != new_state.flipped,
        geometry_changed=old_geometry != new_geometry,
        theme_changed=(
            old_state.board_theme != new_state.board_theme
            or old_state.piece_theme != new_state.piece_theme
            or old_state.annotation_theme != new_state.annotation_theme
        ),
        annotations_changed=old_state.annotations != new_state.annotations,
        selected_square_changed=old_state.selected_square != new_state.selected_square,
        legal_targets_changed=old_state.legal_targets != new_state.legal_targets,
        last_move_changed=old_state.last_move != new_state.last_move,
        flash_changed=old_state.flash != new_state.flash,
        animation_changed=old_state.animation != new_state.animation,
        animation_squares_changed=old_animation_move != new_animation_move,
        drag_piece_changed=old_state.drag_piece != new_state.drag_piece,
        drag_origin_changed=old_drag_origin != new_drag_origin,
        live_arrow_changed=(
            old_state.live_arrow != new_state.live_arrow
            or old_state.live_arrow_color != new_state.live_arrow_color
        ),
        coordinates_visibility_changed=old_state.show_coordinates != new_state.show_coordinates,
        threat_changed=old_state.threat_move != new_state.threat_move,
        control_overlay_changed=old_state.control_overlay != new_state.control_overlay,
    )
