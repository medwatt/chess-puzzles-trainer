from __future__ import annotations

import chess

from chess_puzzles.board.annotations import BoardAnnotations
from chess_puzzles.board.board_state import BoardRenderState, DragPieceState, MoveAnimationState
from chess_puzzles.board.board_theme import PieceTheme
from chess_puzzles.board.canvas_backend import MemoryCanvasBackend
from chess_puzzles.board.control import ControlOverlayMode
from chess_puzzles.board.geometry import BoardGeometry
from chess_puzzles.board.render_coordinator import BoardRenderCoordinator


def test_annotation_update_only_redraws_annotation_layers_and_raises_layers() -> None:
    backend = MemoryCanvasBackend()
    coordinator = BoardRenderCoordinator(backend)
    geometry = BoardGeometry.from_canvas(640, 640)
    state = BoardRenderState(piece_theme=PieceTheme(id="test", name="Test"))

    coordinator.render(state, geometry)
    backend.operations.clear()

    state = state.copy_with(annotations=BoardAnnotations.empty().toggle_arrow(chess.E2, chess.E4))
    coordinator.render(state, geometry)

    cleared_tags = [args[0] for name, args, _options in backend.operations if name == "clear"]
    assert "annotation_squares" in cleared_tags
    assert "annotation_circles" in cleared_tags
    assert "annotation_arrows" in cleared_tags
    assert "pieces" not in cleared_tags
    assert "board_squares" not in cleared_tags


def test_animation_tick_only_redraws_animation_layer() -> None:
    backend = MemoryCanvasBackend()
    coordinator = BoardRenderCoordinator(backend)
    geometry = BoardGeometry.from_canvas(640, 640)
    move = chess.Move.from_uci("e2e4")
    piece = chess.Piece(chess.PAWN, chess.WHITE)
    state = BoardRenderState(
        piece_theme=PieceTheme(id="test", name="Test"),
        animation=MoveAnimationState(move=move, piece=piece, progress=0.2),
    )

    coordinator.render(state, geometry)
    backend.operations.clear()

    state = state.copy_with(animation=MoveAnimationState(move=move, piece=piece, progress=0.6))
    coordinator.render(state, geometry)

    cleared_tags = [args[0] for name, args, _options in backend.operations if name == "clear"]
    assert "animation" in cleared_tags
    assert "pieces" not in cleared_tags
    assert "board_squares" not in cleared_tags


def test_unchanged_render_raises_no_tags() -> None:
    backend = MemoryCanvasBackend()
    coordinator = BoardRenderCoordinator(backend)
    geometry = BoardGeometry.from_canvas(640, 640)
    state = BoardRenderState(piece_theme=PieceTheme(id="test", name="Test"))

    coordinator.render(state, geometry)
    backend.operations.clear()

    coordinator.render(state, geometry)

    assert backend.operations == []


def test_threat_arrow_only_redraws_threat_layer() -> None:
    backend = MemoryCanvasBackend()
    coordinator = BoardRenderCoordinator(backend)
    geometry = BoardGeometry.from_canvas(640, 640)
    state = BoardRenderState(piece_theme=PieceTheme(id="test", name="Test"))

    coordinator.render(state, geometry)
    backend.operations.clear()

    state = state.copy_with(threat_move=chess.Move.from_uci("d8h4"))
    coordinator.render(state, geometry)

    cleared_tags = [args[0] for name, args, _options in backend.operations if name == "clear"]
    assert "threat" in cleared_tags
    assert "pieces" not in cleared_tags
    assert "board_squares" not in cleared_tags
    arrow_items = [name for name, _args, _options in backend.operations if name in {"line", "polygon"}]
    assert arrow_items, "threat arrow should draw a shaft and head"


def test_control_overlay_cycle_only_redraws_overlay_layer() -> None:
    backend = MemoryCanvasBackend()
    coordinator = BoardRenderCoordinator(backend)
    geometry = BoardGeometry.from_canvas(640, 640)
    state = BoardRenderState(piece_theme=PieceTheme(id="test", name="Test"))

    coordinator.render(state, geometry)
    backend.operations.clear()

    state = state.copy_with(control_overlay=ControlOverlayMode.HANGING)
    coordinator.render(state, geometry)

    cleared_tags = [args[0] for name, args, _options in backend.operations if name == "clear"]
    assert "control_overlay" in cleared_tags
    assert "pieces" not in cleared_tags
    assert "board_squares" not in cleared_tags

    backend.operations.clear()
    # A position with a genuinely contested square (White doubles up on d5).
    contested_board = chess.Board("k7/8/4p3/8/8/2N5/8/3R3K w - - 0 1")
    state = state.copy_with(board=contested_board, control_overlay=ControlOverlayMode.CONTROL)
    coordinator.render(state, geometry)

    rectangles = [item for item in backend.operations if item[0] == "rectangle"]
    assert rectangles, "control mode should tint contested squares"
    stipples = {options.get("stipple") for _name, _args, options in rectangles}
    assert stipples & {"gray25", "gray50", "gray75"}, "margin should map to stipple density"


def test_adjacent_contested_markers_stay_inside_their_cells() -> None:
    backend = MemoryCanvasBackend()
    coordinator = BoardRenderCoordinator(backend)
    geometry = BoardGeometry.from_canvas(640, 640)
    # d4 and d5 are both contested with margin +1 (Rd1+Nc3 vs e6 pawn on d5,
    # Rd1+Nf3 vs e5 pawn on d4), giving two vertically adjacent markers.
    board = chess.Board("7k/8/4p3/4p3/8/2N2N2/8/3R3K w - - 0 1")
    state = BoardRenderState(
        piece_theme=PieceTheme(id="test", name="Test"),
        board=board,
        control_overlay=ControlOverlayMode.CONTROL,
    )

    coordinator.render(state, geometry)

    square = geometry.square_size
    d_file_left = geometry.left + 3 * square
    rank_boundary = geometry.top + 4 * square  # edge between d5 and d4 cells
    column_rects = sorted(
        (
            args[1:]
            for name, args, options in backend.operations
            if name == "rectangle"
            and args[0] == "control_overlay"
            and d_file_left <= args[1] < d_file_left + square
        ),
        key=lambda coords: coords[1],
    )
    assert len(column_rects) == 2, f"expected markers on d5 and d4, got {len(column_rects)}"
    (d5_x1, d5_y1, d5_x2, d5_y2), (d4_x1, d4_y1, d4_x2, d4_y2) = column_rects
    border = max(2.0, square * 0.05)
    # Including the outline stroke, each marker stays strictly inside its
    # cell, so neighbouring markers can never produce a ragged shared seam.
    assert d5_y2 + border / 2 < rank_boundary < d4_y1 - border / 2
    assert d5_y1 - border / 2 > rank_boundary - square
    assert d4_y2 + border / 2 < rank_boundary + square
    for x1, x2 in ((d5_x1, d5_x2), (d4_x1, d4_x2)):
        assert x1 - border / 2 > d_file_left
        assert x2 + border / 2 < d_file_left + square


def test_drag_motion_only_redraws_drag_layer_after_drag_starts() -> None:
    backend = MemoryCanvasBackend()
    coordinator = BoardRenderCoordinator(backend)
    geometry = BoardGeometry.from_canvas(640, 640)
    state = BoardRenderState(piece_theme=PieceTheme(id="test", name="Test"))

    coordinator.render(state, geometry)
    state = state.copy_with(
        drag_piece=DragPieceState(
            origin=chess.E2,
            piece=chess.Piece(chess.PAWN, chess.WHITE),
            x=360,
            y=520,
        )
    )
    coordinator.render(state, geometry)
    backend.operations.clear()

    state = state.copy_with(
        drag_piece=DragPieceState(
            origin=chess.E2,
            piece=chess.Piece(chess.PAWN, chess.WHITE),
            x=360,
            y=440,
        )
    )
    coordinator.render(state, geometry)

    cleared_tags = [args[0] for name, args, _options in backend.operations if name == "clear"]
    assert "drag_piece" in cleared_tags
    assert "pieces" not in cleared_tags
    assert "board_squares" not in cleared_tags
