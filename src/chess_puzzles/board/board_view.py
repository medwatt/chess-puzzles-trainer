from __future__ import annotations

import tkinter as tk
import time
from collections.abc import Callable

import chess

from chess_puzzles.board.annotations import AnnotationColor, BoardAnnotations
from chess_puzzles.board.board_state import (
    BoardCapabilities,
    BoardRenderState,
    BoardSnapshot,
    DragPieceState,
    FlashState,
    MoveAnimationState,
)
from chess_puzzles.board.board_theme import AnnotationTheme, BoardTheme, PieceTheme
from chess_puzzles.board.canvas_backend import TkCanvasBackend
from chess_puzzles.board.control import ControlOverlayMode
from chess_puzzles.board.geometry import BoardGeometry
from chess_puzzles.board.images import PieceImageCache
from chess_puzzles.board.input import (
    AnnotationChanged,
    BoardEvent,
    BoardFlipped,
    Modifier,
    MoveRequested,
    SquareSelected,
    event_modifiers,
)
from chess_puzzles.board.render_coordinator import BoardRenderCoordinator
from chess_puzzles.constants import (
    FLASH_DEFAULT_COLOR,
    FLASH_DURATION_MS,
    MOVE_ANIMATION_MS,
    MOVE_ANIMATION_TICK_MS,
)


EventHandler = Callable[[BoardEvent], None]


class BoardView(tk.Canvas):
    """Reusable interactive chess board (a Tk Canvas).

    This manages the visual board state and mouse input. It fires events
    like move-attempted and annotation-changed but does not decide
    whether a move is correct. That logic lives in the puzzle session
    and engine code, outside this class.
    """

    def __init__(
        self,
        master: tk.Misc,
        *,
        state: BoardRenderState | None = None,
        capabilities: BoardCapabilities | None = None,
        width: int = 640,
        height: int = 640,
        event_handler: EventHandler | None = None,
    ) -> None:
        resolved_state = state or BoardRenderState()
        if capabilities is not None:
            resolved_state = resolved_state.copy_with(capabilities=capabilities)
        super().__init__(
            master,
            width=width,
            height=height,
            highlightthickness=0,
            bd=0,
            bg=resolved_state.board_theme.dark_square,
        )
        self._state = resolved_state
        self._event_handlers: list[EventHandler] = []
        if event_handler is not None:
            self._event_handlers.append(event_handler)
        self._geometry = BoardGeometry.from_canvas(width, height)
        self._coordinator = BoardRenderCoordinator(TkCanvasBackend(self))
        self._press_square: int | None = None
        self._press_already_selected: bool = False
        self._drag_offset: tuple[float, float] = (0.0, 0.0)
        self._right_drag_origin: int | None = None
        self._promotion_in_progress: bool = False
        self._piece_images = PieceImageCache()
        self._flash_after_id: str | None = None
        self._animation_after_id: str | None = None
        self._animation_started_at: float | None = None
        self._drag_render_pending: bool = False
        self._surround_bg = self._state.board_theme.dark_square

        self.bind("<Configure>", self._on_resize)
        self.bind("<ButtonPress-1>", self._on_left_press)
        self.bind("<B1-Motion>", self._on_left_drag)
        self.bind("<ButtonRelease-1>", self._on_left_release)
        self.bind("<ButtonPress-3>", self._on_right_press)
        self.bind("<B3-Motion>", self._on_right_drag)
        self.bind("<ButtonRelease-3>", self._on_right_release)
        self.bind("<Escape>", lambda _event: self.clear_annotations())

        self.render()

    @property
    def state(self) -> BoardRenderState:
        return self._state

    def set_position(self, board_or_fen: chess.Board | str) -> None:
        self.cancel_animation()
        board = chess.Board(board_or_fen) if isinstance(board_or_fen, str) else board_or_fen.copy(stack=False)
        self._set_state(
            self._state.copy_with(
                board=board,
                selected_square=None,
                legal_targets=frozenset(),
                animation=None,
                drag_piece=None,
                threat_move=None,
            )
        )

    def advance_position(
        self,
        board_or_fen: chess.Board | str,
        move: chess.Move | None,
        *,
        clear_annotations: bool = True,
        animate: bool = True,
    ) -> None:
        self.cancel_animation()
        previous_board = self._state.board
        board = chess.Board(board_or_fen) if isinstance(board_or_fen, str) else board_or_fen.copy(stack=False)
        annotations = BoardAnnotations.empty() if clear_annotations else self._state.annotations
        animation = None
        if move is not None and animate:
            piece = previous_board.piece_at(move.from_square)
            if piece is not None:
                animation = MoveAnimationState(move=move, piece=piece, progress=0.0)
        self._set_state(
            self._state.copy_with(
                board=board,
                annotations=annotations,
                selected_square=None,
                legal_targets=frozenset(),
                last_move=move,
                animation=animation,
                drag_piece=None,
                threat_move=None,
            )
        )
        if animation is not None:
            self._start_animation_timer()

    def set_orientation(self, color_or_orientation: chess.Color | bool | str) -> None:
        if isinstance(color_or_orientation, str):
            flipped = color_or_orientation.lower() in {"black", "flipped"}
        else:
            flipped = color_or_orientation == chess.BLACK
        self.set_flipped(flipped)

    def set_flipped(self, flipped: bool) -> None:
        self._set_state(self._state.copy_with(flipped=flipped))
        self._emit(BoardFlipped(flipped))

    def set_theme(
        self,
        board_theme: BoardTheme,
        piece_theme: PieceTheme | None = None,
        annotation_theme: AnnotationTheme | None = None,
    ) -> None:
        changes: dict[str, object] = {"board_theme": board_theme}
        if piece_theme is not None:
            changes["piece_theme"] = piece_theme
        if annotation_theme is not None:
            changes["annotation_theme"] = annotation_theme
        self._set_state(self._state.copy_with(**changes))

    def set_surround_background(self, color: str) -> None:
        self._surround_bg = color
        self.configure(bg=color)

    def set_coordinates_visible(self, enabled: bool) -> None:
        self._set_state(self._state.copy_with(show_coordinates=enabled))

    def set_selected_square(self, square: int | None) -> None:
        self._set_state(self._state.copy_with(selected_square=square, legal_targets=frozenset()))
        self._emit(SquareSelected(square))

    def show_hint_square(self, square: int) -> None:
        self._select_square(square)

    def set_annotations(self, annotations: BoardAnnotations) -> None:
        self._set_state(self._state.copy_with(annotations=annotations))
        self._emit(AnnotationChanged(annotations))

    def clear_annotations(self) -> None:
        self.set_annotations(BoardAnnotations.empty())

    def set_last_move(self, move: chess.Move | None) -> None:
        self._set_state(self._state.copy_with(last_move=move))

    def set_threat_move(self, move: chess.Move | None) -> None:
        """Show (or clear) the opponent-threat arrow.

        The arrow is position-specific, so any position change clears it
        automatically.
        """
        self._set_state(self._state.copy_with(threat_move=move))

    def set_control_overlay(self, mode: ControlOverlayMode) -> None:
        self._set_state(self._state.copy_with(control_overlay=mode))

    def flash_move(self, move: chess.Move, style: str = FLASH_DEFAULT_COLOR, duration_ms: int = FLASH_DURATION_MS) -> None:
        if self._flash_after_id is not None:
            self.after_cancel(self._flash_after_id)
        self._set_state(self._state.copy_with(flash=FlashState((move.from_square, move.to_square), style), drag_piece=None))
        self._flash_after_id = self.after(duration_ms, self._clear_flash)

    def cancel_animation(self) -> None:
        if self._animation_after_id is not None:
            self.after_cancel(self._animation_after_id)
            self._animation_after_id = None
        self._animation_started_at = None
        if self._state.animation is not None:
            self._set_state(self._state.copy_with(animation=None))

    def snapshot_for_export(self) -> BoardSnapshot:
        return BoardSnapshot(state=self._state, width=int(self._geometry.side), height=int(self._geometry.side))

    def render(self) -> None:
        self._coordinator.render(self._state, self._geometry)

    def _set_state(self, state: BoardRenderState) -> None:
        self._state = state
        self.render()

    def _emit(self, event: BoardEvent) -> None:
        for handler in tuple(self._event_handlers):
            handler(event)

    def _on_resize(self, event: tk.Event) -> None:
        self._geometry = BoardGeometry.from_canvas(int(event.width), int(event.height))
        self.render()

    def _on_left_press(self, event: tk.Event) -> None:
        if self._state.capabilities.select_any_square:
            if self._promotion_in_progress:
                return
            square = self._square_from_event(event)
            if square is not None:
                self._emit(SquareSelected(square))
            return
        if not self._state.capabilities.movable_pieces or self._promotion_in_progress:
            return
        square = self._square_from_event(event)
        self._press_square = square
        self._press_already_selected = square is not None and self._state.selected_square == square
        if square is not None and self._is_selectable_piece(square):
            cx, cy = self._geometry.square_center(square, self._state.flipped)
            self._drag_offset = (cx - float(event.x), cy - float(event.y))
            self._select_square(square)

    def _on_left_drag(self, event: tk.Event) -> None:
        if self._state.capabilities.select_any_square:
            return
        if not self._state.capabilities.movable_pieces or self._promotion_in_progress:
            return
        origin = self._press_square
        if origin is None or not self._is_selectable_piece(origin):
            return
        piece = self._state.board.piece_at(origin)
        if piece is None:
            return
        offset_x, offset_y = self._drag_offset
        is_first_drag = self._state.drag_piece is None
        self._state = self._state.copy_with(
            drag_piece=DragPieceState(
                origin=origin,
                piece=piece,
                x=float(event.x) + offset_x,
                y=float(event.y) + offset_y,
            )
        )
        if is_first_drag:
            self.render()
        if not self._drag_render_pending:
            self._drag_render_pending = True
            self.after_idle(self._flush_drag_render)

    def _on_left_release(self, event: tk.Event) -> None:
        if self._state.capabilities.select_any_square:
            return
        if not self._state.capabilities.movable_pieces or self._promotion_in_progress:
            return
        origin = self._press_square
        target = self._square_from_event(event)
        was_already_selected = self._press_already_selected
        was_dragging = self._state.drag_piece is not None
        self._press_square = None
        self._press_already_selected = False
        self._drag_offset = (0.0, 0.0)
        if target is None:
            self._clear_drag_piece()
            return
        if origin is None:
            selected = self._state.selected_square
            if selected is not None:
                self._emit_move(selected, target)
            else:
                self._clear_drag_piece()
            return
        if origin == target:
            selected = self._state.selected_square
            if self._is_selectable_piece(origin):
                if was_already_selected:
                    self.set_selected_square(None)
                self._clear_drag_piece()
            elif selected is not None:
                self._emit_move(selected, target)
            else:
                self._clear_drag_piece()
            return
        if self._is_selectable_piece(origin):
            self._emit_move(origin, target, animate=not was_dragging)
        elif self._state.selected_square is not None:
            self._emit_move(self._state.selected_square, target)

    def _on_right_press(self, event: tk.Event) -> None:
        if not self._state.capabilities.annotations:
            return
        self._right_drag_origin = self._square_from_event(event)
        color = _annotation_color(event_modifiers(int(event.state)))
        self._set_state(self._state.copy_with(live_arrow_color=color))

    def _on_right_drag(self, event: tk.Event) -> None:
        if self._right_drag_origin is None or not self._state.capabilities.annotations:
            return
        target = self._square_from_event(event)
        live_arrow = (self._right_drag_origin, target) if target is not None and target != self._right_drag_origin else None
        color = _annotation_color(event_modifiers(int(event.state)))
        self._set_state(self._state.copy_with(live_arrow=live_arrow, live_arrow_color=color))

    def _on_right_release(self, event: tk.Event) -> None:
        origin = self._right_drag_origin
        self._right_drag_origin = None
        self._set_state(self._state.copy_with(live_arrow=None))
        if origin is None or not self._state.capabilities.annotations:
            return
        target = self._square_from_event(event)
        if target is None:
            return
        modifiers = event_modifiers(int(event.state))
        color = _annotation_color(modifiers)
        if target == origin:
            if Modifier.ALT in modifiers:
                annotations = self._state.annotations.toggle_square(origin, color)
            else:
                annotations = self._state.annotations.toggle_circle(origin, color)
        else:
            annotations = self._state.annotations.toggle_arrow(origin, target, color)
        self.set_annotations(annotations)

    def _square_from_event(self, event: tk.Event) -> int | None:
        return self._geometry.square_at_pixel(float(event.x), float(event.y), self._state.flipped)

    def _clear_flash(self) -> None:
        self._flash_after_id = None
        self._set_state(self._state.copy_with(flash=None))

    def _flush_drag_render(self) -> None:
        self._drag_render_pending = False
        self.render()

    def _clear_drag_piece(self) -> None:
        if self._state.drag_piece is not None:
            self._set_state(self._state.copy_with(drag_piece=None))

    def _is_selectable_piece(self, square: int) -> bool:
        piece = self._state.board.piece_at(square)
        return piece is not None and piece.color == self._state.board.turn

    def _select_square(self, square: int) -> None:
        legal_targets = frozenset(move.to_square for move in self._state.board.legal_moves if move.from_square == square)
        self._set_state(self._state.copy_with(selected_square=square, legal_targets=legal_targets))
        self._emit(SquareSelected(square))

    def _emit_move(self, origin: int, target: int, *, animate: bool = True) -> None:
        piece = self._state.board.piece_at(origin)
        promotion_piece: chess.PieceType | None = None
        if (
            piece is not None
            and piece.piece_type == chess.PAWN
            and chess.square_rank(target) in {0, 7}
            and chess.Move(origin, target, promotion=chess.QUEEN) in self._state.board.legal_moves
        ):
            promotion_piece = self._show_promotion_dialog(target, piece.color)
            if promotion_piece is None:
                self._clear_drag_piece()
                return
        move = chess.Move(origin, target, promotion=promotion_piece) if promotion_piece else chess.Move(origin, target)
        self._set_state(self._state.copy_with(selected_square=None, legal_targets=frozenset()))
        self._emit(MoveRequested(move, animate=animate))
        self._clear_drag_piece()

    def _show_promotion_dialog(self, to_square: int, color: chess.Color) -> chess.PieceType | None:
        pieces = (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT)
        display_file, display_rank = self._geometry.display_coords(to_square, self._state.flipped)
        square_size = self._geometry.square_size
        target_size = max(16, int(square_size * 0.88))
        step = 1 if display_rank == 0 else -1
        result: list[chess.PieceType | None] = [None]
        done = tk.BooleanVar(self, value=False)
        window_ids: list[int] = []
        kept_images: list[tk.PhotoImage] = []

        def pick(piece_type: chess.PieceType) -> None:
            result[0] = piece_type
            done.set(True)

        self._promotion_in_progress = True
        directory = self._state.piece_theme.image_directory
        for index, piece_type in enumerate(pieces):
            row = display_rank + step * index
            x = self._geometry.left + (display_file + 0.5) * square_size
            y = self._geometry.top + (row + 0.5) * square_size
            button = tk.Button(self, relief=tk.RAISED, bd=2, cursor="hand2", command=lambda pt=piece_type: pick(pt))
            image = (
                self._piece_images.image_for(chess.Piece(piece_type, color), directory, target_size)
                if directory is not None
                else None
            )
            if image is not None:
                button.configure(image=image)
                kept_images.append(image)
            else:
                button.configure(text=chess.piece_symbol(piece_type).upper(), font=("TkDefaultFont", 14, "bold"))
            window_ids.append(self.create_window(x, y, window=button, width=int(square_size), height=int(square_size)))

        escape_id = self.bind("<Escape>", lambda _event: done.set(True), add=True)
        self.focus_set()
        self.wait_variable(done)
        self.unbind("<Escape>", escape_id)
        for window_id in window_ids:
            self.delete(window_id)
        self._promotion_in_progress = False
        return result[0]

    def _start_animation_timer(self) -> None:
        self._animation_started_at = time.monotonic()
        self._schedule_animation_tick()

    def _schedule_animation_tick(self) -> None:
        if self._animation_after_id is not None:
            self.after_cancel(self._animation_after_id)
        self._animation_after_id = self.after(MOVE_ANIMATION_TICK_MS, self._advance_animation)

    def _advance_animation(self) -> None:
        self._animation_after_id = None
        animation = self._state.animation
        if animation is None or self._animation_started_at is None:
            return
        elapsed_ms = (time.monotonic() - self._animation_started_at) * 1000
        linear = min(1.0, elapsed_ms / MOVE_ANIMATION_MS)
        progress = 1 - pow(1 - linear, 3)
        if progress >= 1:
            self._animation_started_at = None
            self._set_state(self._state.copy_with(animation=None))
            return
        self._set_state(self._state.copy_with(animation=MoveAnimationState(animation.move, animation.piece, progress)))
        self._schedule_animation_tick()


def _annotation_color(modifiers: frozenset[Modifier]) -> AnnotationColor:
    if Modifier.SHIFT in modifiers:
        return AnnotationColor.RED
    if Modifier.CONTROL in modifiers:
        return AnnotationColor.BLUE
    return AnnotationColor.GREEN
