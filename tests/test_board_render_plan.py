from __future__ import annotations

import chess

from chess_puzzles.board.annotations import BoardAnnotations
from chess_puzzles.board.board_state import BoardRenderState, DragPieceState, MoveAnimationState
from chess_puzzles.board.control import ControlOverlayMode
from chess_puzzles.board.geometry import BoardGeometry
from chess_puzzles.board.render_plan import calculate_changes


def test_annotation_change_does_not_dirty_position_or_pieces() -> None:
    geometry = BoardGeometry.from_canvas(640, 640)
    old_state = BoardRenderState()
    new_state = old_state.copy_with(annotations=BoardAnnotations.empty().toggle_circle(chess.E4))

    changes = calculate_changes(old_state, new_state, geometry, geometry)

    assert changes.annotations_changed
    assert not changes.position_changed
    assert not changes.pieces_changed


def test_advancing_position_dirties_pieces_and_last_move() -> None:
    geometry = BoardGeometry.from_canvas(640, 640)
    old_state = BoardRenderState()
    board = old_state.board.copy(stack=False)
    move = chess.Move.from_uci("e2e4")
    board.push(move)
    new_state = old_state.copy_with(board=board, last_move=move)

    changes = calculate_changes(old_state, new_state, geometry, geometry)

    assert changes.position_changed
    assert changes.pieces_changed
    assert changes.last_move_changed
    assert not changes.annotations_changed


def test_drag_motion_does_not_dirty_piece_layer_origin() -> None:
    geometry = BoardGeometry.from_canvas(640, 640)
    old_state = BoardRenderState(
        drag_piece=DragPieceState(
            origin=chess.E2,
            piece=chess.Piece(chess.PAWN, chess.WHITE),
            x=320,
            y=500,
        )
    )
    new_state = old_state.copy_with(
        drag_piece=DragPieceState(
            origin=chess.E2,
            piece=chess.Piece(chess.PAWN, chess.WHITE),
            x=320,
            y=420,
        )
    )

    changes = calculate_changes(old_state, new_state, geometry, geometry)

    assert changes.drag_piece_changed
    assert not changes.drag_origin_changed
    assert not changes.pieces_changed


def test_animation_progress_tick_does_not_dirty_animation_squares() -> None:
    geometry = BoardGeometry.from_canvas(640, 640)
    move = chess.Move.from_uci("e2e4")
    piece = chess.Piece(chess.PAWN, chess.WHITE)
    old_state = BoardRenderState(animation=MoveAnimationState(move=move, piece=piece, progress=0.2))
    new_state = old_state.copy_with(animation=MoveAnimationState(move=move, piece=piece, progress=0.6))

    changes = calculate_changes(old_state, new_state, geometry, geometry)

    assert changes.animation_changed
    assert not changes.animation_squares_changed
    assert not changes.position_changed


def test_animation_end_dirties_animation_squares() -> None:
    geometry = BoardGeometry.from_canvas(640, 640)
    move = chess.Move.from_uci("e2e4")
    piece = chess.Piece(chess.PAWN, chess.WHITE)
    old_state = BoardRenderState(animation=MoveAnimationState(move=move, piece=piece, progress=0.9))
    new_state = old_state.copy_with(animation=None)

    changes = calculate_changes(old_state, new_state, geometry, geometry)

    assert changes.animation_changed
    assert changes.animation_squares_changed


def test_threat_and_control_overlay_changes_are_isolated() -> None:
    geometry = BoardGeometry.from_canvas(640, 640)
    old_state = BoardRenderState()
    new_state = old_state.copy_with(
        threat_move=chess.Move.from_uci("d8h4"),
        control_overlay=ControlOverlayMode.HANGING,
    )

    changes = calculate_changes(old_state, new_state, geometry, geometry)

    assert changes.threat_changed
    assert changes.control_overlay_changed
    assert not changes.position_changed
    assert not changes.pieces_changed
    assert not changes.annotations_changed


def test_drag_start_dirties_piece_layer_origin() -> None:
    geometry = BoardGeometry.from_canvas(640, 640)
    old_state = BoardRenderState()
    new_state = old_state.copy_with(
        drag_piece=DragPieceState(
            origin=chess.E2,
            piece=chess.Piece(chess.PAWN, chess.WHITE),
            x=320,
            y=500,
        )
    )

    changes = calculate_changes(old_state, new_state, geometry, geometry)

    assert changes.drag_piece_changed
    assert changes.drag_origin_changed
