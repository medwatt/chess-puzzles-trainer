from __future__ import annotations

import html
import re

import chess

from chess_puzzles.board.board_state import BoardRenderState, BoardSnapshot
from chess_puzzles.board.geometry import BoardGeometry
from chess_puzzles.board.render_geometry import (
    arrow_shape,
    coordinate_cap_height,
    coordinate_font_size,
    coordinate_labels,
    square_fill,
)


def snapshot_to_svg(snapshot: BoardSnapshot) -> str:
    geometry = BoardGeometry.from_canvas(snapshot.width, snapshot.height)
    return state_to_svg(snapshot.state, geometry)


def state_to_svg(state: BoardRenderState, geometry: BoardGeometry) -> str:
    parts = [
        _header(geometry),
        _squares(state, geometry),
        _coordinates(state, geometry) if state.show_coordinates else "",
        _selection(state, geometry),
        _annotation_squares(state, geometry),
        _annotation_circles(state, geometry),
        _pieces(state, geometry),
        _annotation_arrows(state, geometry),
        _last_move(state, geometry),
        _flash(state, geometry),
        "</svg>",
    ]
    return "\n".join(part for part in parts if part)


def _header(geometry: BoardGeometry) -> str:
    width = _fmt(geometry.side)
    height = _fmt(geometry.side)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img">'
    )


def _squares(state: BoardRenderState, geometry: BoardGeometry) -> str:
    parts: list[str] = []
    for square in chess.SQUARES:
        x, y = geometry.square_top_left(square, state.flipped)
        parts.append(_rect(x, y, geometry.square_size, geometry.square_size, fill=square_fill(state, square)))
    return "\n".join(parts)


_SVG_TEXT_ANCHORS = {"se": "end", "nw": "start"}


def _coordinates(state: BoardRenderState, geometry: BoardGeometry) -> str:
    size = coordinate_font_size(geometry)
    cap = coordinate_cap_height(geometry)
    parts: list[str] = []
    for label in coordinate_labels(state, geometry):
        # Position every label by its baseline (the default "alphabetic"), which
        # renders the same in every SVG viewer. Rank digits ("nw") hang from the
        # top edge, so drop their baseline by the cap height.
        y = label.y + cap if label.anchor == "nw" else label.y
        parts.append(_text(label.x, y, label.text, label.color, size, _SVG_TEXT_ANCHORS[label.anchor]))
    return "\n".join(parts)


def _selection(state: BoardRenderState, geometry: BoardGeometry) -> str:
    parts: list[str] = []
    if state.selected_square is not None:
        x, y = geometry.square_top_left(state.selected_square, state.flipped)
        parts.append(
            _rect(
                x,
                y,
                geometry.square_size,
                geometry.square_size,
                fill=state.board_theme.selected_square,
                opacity=0.55,
            )
        )
    if state.capabilities.legal_move_hints:
        radius = geometry.square_size * 0.14
        for square in state.legal_targets:
            cx, cy = geometry.square_center(square, state.flipped)
            parts.append(
                f'<circle cx="{_fmt(cx)}" cy="{_fmt(cy)}" r="{_fmt(radius)}" '
                f'fill="{html.escape(state.board_theme.legal_target)}"/>'
            )
    return "\n".join(parts)


def _annotation_squares(state: BoardRenderState, geometry: BoardGeometry) -> str:
    if not state.capabilities.annotations:
        return ""
    width = max(2.0, geometry.square_size * state.annotation_theme.square_stroke_scale)
    parts: list[str] = []
    for mark in state.annotations.squares:
        x, y = geometry.square_top_left(mark.square, state.flipped)
        color = state.annotation_theme.colors[mark.color]
        parts.append(
            _rect(
                x + width / 2,
                y + width / 2,
                geometry.square_size - width,
                geometry.square_size - width,
                fill="none",
                stroke=color,
                stroke_width=width,
            )
        )
    return "\n".join(parts)


def _annotation_circles(state: BoardRenderState, geometry: BoardGeometry) -> str:
    if not state.capabilities.annotations:
        return ""
    width = max(2.0, geometry.square_size * state.annotation_theme.square_stroke_scale)
    radius = geometry.square_size * state.annotation_theme.circle_radius_scale
    parts: list[str] = []
    for circle in state.annotations.circles:
        cx, cy = geometry.square_center(circle.square, state.flipped)
        color = state.annotation_theme.colors[circle.color]
        parts.append(
            f'<circle cx="{_fmt(cx)}" cy="{_fmt(cy)}" r="{_fmt(radius)}" fill="none" '
            f'stroke="{html.escape(color)}" stroke-width="{_fmt(width)}"/>'
        )
    return "\n".join(parts)


def _pieces(state: BoardRenderState, geometry: BoardGeometry) -> str:
    if state.piece_theme.svg_directory is None:
        return ""
    try:
        svg_sources = _piece_svg_sources(state.piece_theme.svg_directory)
    except FileNotFoundError:
        return ""
    return _svg_pieces(state, geometry, svg_sources)


def _svg_pieces(state: BoardRenderState, geometry: BoardGeometry, pieces: dict[str, str]) -> str:
    parts: list[str] = []
    piece_size = geometry.square_size * state.piece_theme.scale
    inset = (geometry.square_size - piece_size) / 2
    for square, piece in state.board.piece_map().items():
        key = _piece_key(piece)
        source = pieces.get(key)
        if source is None:
            continue
        x, y = geometry.square_top_left(square, state.flipped)
        piece_id = f"{key}_{chess.square_name(square)}"
        parts.append(_inline_piece_svg(source, piece_id, x + inset, y + inset, piece_size))
    return "\n".join(parts)


def _annotation_arrows(state: BoardRenderState, geometry: BoardGeometry) -> str:
    if not state.capabilities.annotations:
        return ""
    parts = [
        _arrow(
            state,
            geometry,
            arrow.origin,
            arrow.target,
            state.annotation_theme.colors[arrow.color],
            state.annotation_theme.arrow_stroke_scale,
        )
        for arrow in state.annotations.arrows
    ]
    if state.live_arrow is not None:
        origin, target = state.live_arrow
        color = state.annotation_theme.colors[state.live_arrow_color]
        parts.append(_arrow(state, geometry, origin, target, color, state.annotation_theme.arrow_stroke_scale))
    return "\n".join(part for part in parts if part)


def _last_move(state: BoardRenderState, geometry: BoardGeometry) -> str:
    if not state.capabilities.last_move or state.last_move is None:
        return ""
    return _arrow(
        state,
        geometry,
        state.last_move.from_square,
        state.last_move.to_square,
        state.annotation_theme.last_move_color,
        state.annotation_theme.last_move_stroke_scale,
    )


def _flash(state: BoardRenderState, geometry: BoardGeometry) -> str:
    if state.flash is None:
        return ""
    parts: list[str] = []
    for square in state.flash.squares:
        x, y = geometry.square_top_left(square, state.flipped)
        parts.append(
            _rect(
                x,
                y,
                geometry.square_size,
                geometry.square_size,
                fill=state.flash.color,
                opacity=state.annotation_theme.flash_opacity,
            )
        )
    return "\n".join(parts)


def _arrow(
    state: BoardRenderState,
    geometry: BoardGeometry,
    origin: int,
    target: int,
    color: str,
    width_scale: float,
) -> str:
    shape = arrow_shape(geometry, state.annotation_theme, origin, target, state.flipped, width_scale)
    if shape is None:
        return ""
    (start_x, start_y), (end_x, end_y) = shape.shaft_start, shape.shaft_end
    points = " ".join(f"{_fmt(shape.head[i])},{_fmt(shape.head[i + 1])}" for i in (0, 2, 4))
    color_escaped = html.escape(color)
    return (
        f'<line x1="{_fmt(start_x)}" y1="{_fmt(start_y)}" x2="{_fmt(end_x)}" y2="{_fmt(end_y)}" '
        f'stroke="{color_escaped}" stroke-width="{_fmt(shape.width)}" stroke-linecap="round"/>\n'
        f'<polygon points="{points}" fill="{color_escaped}" stroke="{color_escaped}"/>'
    )


def _rect(
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    fill: str,
    stroke: str = "",
    stroke_width: float = 1,
    opacity: float | None = None,
) -> str:
    attrs = [
        f'x="{_fmt(x)}"',
        f'y="{_fmt(y)}"',
        f'width="{_fmt(width)}"',
        f'height="{_fmt(height)}"',
        f'fill="{html.escape(fill)}"',
    ]
    if stroke:
        attrs.append(f'stroke="{html.escape(stroke)}"')
        attrs.append(f'stroke-width="{_fmt(stroke_width)}"')
    if opacity is not None:
        attrs.append(f'opacity="{_fmt(opacity)}"')
    return f"<rect {' '.join(attrs)}/>"


def _text(x: float, y: float, value: str, fill: str, size: int, anchor: str) -> str:
    return (
        f'<text x="{_fmt(x)}" y="{_fmt(y)}" fill="{html.escape(fill)}" '
        f'font-family="DejaVu Sans, Arial, sans-serif" font-size="{size}" font-weight="normal" '
        f'text-anchor="{anchor}" dominant-baseline="alphabetic">{html.escape(value)}</text>'
    )


def _fmt(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.3f}".rstrip("0").rstrip(".")


def _piece_svg_sources(piece_directory: object) -> dict[str, str]:
    directory = getattr(piece_directory, "resolve", lambda: piece_directory)()
    pieces: dict[str, str] = {}
    missing: list[str] = []
    for color in ("w", "b"):
        for role in ("K", "Q", "R", "B", "N", "P"):
            key = f"{color}{role}"
            path = directory / f"{key}.svg"
            if path.exists():
                pieces[key] = path.read_text(encoding="utf-8")
            else:
                missing.append(path.name)
    if missing:
        missing_text = ", ".join(missing)
        raise FileNotFoundError(f"Missing SVG piece files in {directory}: {missing_text}")
    return pieces


def _inline_piece_svg(source: str, prefix: str, x: float, y: float, size: float) -> str:
    inner = _svg_inner_markup(source)
    inner = _prefix_svg_ids(inner, prefix)
    return (
        f'<svg x="{_fmt(x)}" y="{_fmt(y)}" width="{_fmt(size)}" height="{_fmt(size)}" '
        f'viewBox="0 0 50 50" overflow="visible">\n{inner}\n</svg>'
    )


def _svg_inner_markup(source: str) -> str:
    match = re.search(r"<svg\b[^>]*>(?P<body>.*)</svg>\s*$", source, flags=re.DOTALL)
    if match is None:
        raise ValueError("Piece file does not contain an SVG root element")
    return match.group("body")


def _prefix_svg_ids(markup: str, prefix: str) -> str:
    ids = re.findall(r'\bid="([^"]+)"', markup)
    for svg_id in ids:
        prefixed = f"{prefix}_{svg_id}"
        markup = re.sub(rf'\bid="{re.escape(svg_id)}"', f'id="{prefixed}"', markup)
        markup = markup.replace(f"url(#{svg_id})", f"url(#{prefixed})")
        markup = markup.replace(f'href="#{svg_id}"', f'href="#{prefixed}"')
        markup = markup.replace(f'xlink:href="#{svg_id}"', f'xlink:href="#{prefixed}"')
    return markup


def _piece_key(piece: chess.Piece) -> str:
    color = "w" if piece.color == chess.WHITE else "b"
    role = {
        chess.KING: "K",
        chess.QUEEN: "Q",
        chess.ROOK: "R",
        chess.BISHOP: "B",
        chess.KNIGHT: "N",
        chess.PAWN: "P",
    }[piece.piece_type]
    return f"{color}{role}"
