from __future__ import annotations

import chess

from chess_puzzles.board.annotations import BoardAnnotations
from chess_puzzles.board.board_state import BoardRenderState, BoardSnapshot
from chess_puzzles.board.board_theme import PieceTheme
from chess_puzzles.board.svg_backend import snapshot_to_svg
from chess_puzzles.platform.paths import assets_dir


def test_svg_uses_state_theme_annotations_coordinates_and_last_move() -> None:
    move = chess.Move.from_uci("e2e4")
    state = BoardRenderState(
        show_coordinates=True,
        annotations=BoardAnnotations.empty().toggle_circle(chess.E4).toggle_arrow(chess.G1, chess.F3),
        last_move=move,
    )
    svg = snapshot_to_svg(BoardSnapshot(state=state, width=640, height=640))

    assert svg.startswith("<svg ")
    assert 'fill="#f0d9b5"' in svg
    assert 'fill="#b58863"' in svg
    assert "\u2654" not in svg
    assert ">a<" in svg
    assert 'stroke="#2f8f46"' in svg
    assert 'stroke="#6f6f6f"' in svg


def test_svg_square_parity_matches_live_board() -> None:
    # a1 is a dark square; the SVG export once inverted the board colors.
    svg = snapshot_to_svg(BoardSnapshot(state=BoardRenderState(), width=640, height=640))
    assert '<rect x="0" y="560" width="80" height="80" fill="#b58863"/>' in svg

    flipped_svg = snapshot_to_svg(BoardSnapshot(state=BoardRenderState(flipped=True), width=640, height=640))
    assert '<rect x="560" y="0" width="80" height="80" fill="#b58863"/>' in flipped_svg


def test_svg_embeds_vector_piece_assets_when_piece_theme_has_directory() -> None:
    state = BoardRenderState(
        piece_theme=PieceTheme(
            id="merida",
            name="Merida",
            svg_directory=assets_dir() / "svg" / "pieces" / "Merida",
        )
    )

    svg = snapshot_to_svg(BoardSnapshot(state=state, width=400, height=400))

    assert "<image" not in svg
    assert 'data:image/svg+xml;base64,' not in svg
    assert "<path" in svg
    assert 'id="wR_a1_' in svg
