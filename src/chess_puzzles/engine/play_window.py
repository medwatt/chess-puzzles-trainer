from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import chess

from chess_puzzles.board import ArrowAnnotation, BoardCapabilities, BoardPresenter, BoardShortcuts
from chess_puzzles.board.annotations import AnnotationColor, BoardAnnotations
from chess_puzzles.board.input import BoardEvent, MoveRequested
from chess_puzzles.constants import (
    COMPUTER_REPLY_DELAY_MS,
    ENGINE_POLL_INTERVAL_MS,
    PLAY_WINDOW_GEOMETRY,
    PLAY_WINDOW_MINSIZE,
)
from chess_puzzles.engine.board_analysis_frame import BoardAnalysisFrame
from chess_puzzles.engine.config import EngineDefinition
from chess_puzzles.engine.play_controller import EnginePlayController
from chess_puzzles.engine.play_session import EnginePlaySession
from chess_puzzles.platform.audio import AudioPlayer


class EnginePlayWindow(tk.Toplevel):
    """Free-play window where the user plays a position against the engine."""

    def __init__(
        self,
        parent: tk.Misc,
        initial_board: chess.Board,
        human_color: chess.Color,
        engine: EngineDefinition,
        *,
        presenter: BoardPresenter,
        audio: AudioPlayer,
        title: str,
        evaluation_bar_visible: bool,
    ) -> None:
        super().__init__(parent, name="engineplay", class_="ChessPuzzlesEnginePlay")
        self.title(f"Play vs Engine - {title}")
        self.minsize(*PLAY_WINDOW_MINSIZE)
        self.geometry(PLAY_WINDOW_GEOMETRY)
        # Modeless work window: keep native minimize/maximize controls.
        self._presenter = presenter
        self._audio = audio
        self.session = EnginePlaySession(initial_board, human_color)
        self.controller = EnginePlayController(engine)
        self._thinking = False
        self._engine_after_id: str | None = None
        self._best_move_hint: chess.Move | None = None
        self.status_var = tk.StringVar(value="Your move.")

        root = ttk.Frame(self, padding=(8, 8, 8, 0))
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        self.frame = BoardAnalysisFrame(
            root,
            capabilities=BoardCapabilities(movable_pieces=True, annotations=True, legal_move_hints=True),
            event_handler=self._handle_board_event,
            evaluation_bar_visible=evaluation_bar_visible,
        )
        self.frame.grid(row=0, column=0, sticky="nsew")
        self.board = self.frame.board
        self.evaluation_bar = self.frame.evaluation_bar
        self._presenter.register(self.board)
        self.board.set_orientation(human_color)
        self.evaluation_bar.set_flipped(human_color == chess.BLACK)
        BoardShortcuts(self, self.board).bind()

        controls = ttk.Frame(root)
        controls.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        ttk.Button(controls, text="Reset Position", command=self.reset_position, takefocus=False).pack(side=tk.LEFT)
        ttk.Button(controls, text="Takeback", command=self.takeback, takefocus=False).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(controls, text="Engine Move", command=self.engine_move, takefocus=False).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(controls, text="Close", command=self.close, takefocus=False).pack(side=tk.RIGHT)

        ttk.Label(self, textvariable=self.status_var, anchor=tk.W, padding=(8, 3), relief=tk.SUNKEN).pack(
            fill=tk.X,
            side=tk.BOTTOM,
        )

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Destroy>", self._on_destroy)
        self._refresh_board(snap=True)
        self._request_position_analysis()
        if not self.session.is_human_turn:
            self._schedule_engine_move()
        self.after(ENGINE_POLL_INTERVAL_MS, self._poll_engine_results)

    def reset_position(self) -> None:
        self.session.reset()
        self._cancel_engine()
        self._best_move_hint = None
        self.evaluation_bar.clear()
        self.status_var.set("Position reset. Your move.")
        self._refresh_board(snap=True)
        self._request_position_analysis()
        if not self.session.is_human_turn:
            self._schedule_engine_move()

    def close(self) -> None:
        self.controller.shutdown()
        self.destroy()

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget is self:
            self._presenter.unregister(self.board)

    def _handle_board_event(self, event: BoardEvent) -> None:
        if isinstance(event, MoveRequested):
            self._on_user_move(event.move, animate=event.animate)

    def _on_user_move(self, move: chess.Move, *, animate: bool = True) -> None:
        board_before = self.session.board.copy(stack=False)
        accepted = self.session.play_user_move(move)
        if accepted is None:
            self._audio.play_error()
            self.board.flash_move(move)
            self.status_var.set("Illegal move.")
            return
        # Any accepted move (own or forced for the engine) invalidates scheduled
        # engine moves and in-flight analysis of the previous position.
        self._cancel_engine()
        self._audio.play_move(board_before, accepted, self.session.board)
        self._refresh_board(animated_move=accepted, animate=animate)
        hint = self._best_move_hint
        self._best_move_hint = None
        if hint is not None and hint != accepted:
            self.board.set_annotations(
                BoardAnnotations(arrows=(ArrowAnnotation(hint.from_square, hint.to_square, AnnotationColor.YELLOW),))
            )
        if self.session.board.is_game_over():
            self.status_var.set(self._game_over_text())
            return
        if self.session.is_human_turn:
            self.status_var.set("Your move.")
            self._request_position_analysis()
        else:
            self._schedule_engine_move()

    def takeback(self) -> None:
        if self.session.takeback() is None:
            self.status_var.set("Nothing to take back.")
            return
        self._cancel_engine()
        self._best_move_hint = None
        self._refresh_board(snap=True)
        self._request_position_analysis()
        if self.session.is_human_turn:
            self.status_var.set("Your move.")
        else:
            self.status_var.set("Engine's turn: play its move yourself, or press Engine Move.")

    def engine_move(self) -> None:
        if self._thinking:
            self.status_var.set("Engine is thinking.")
            return
        if self.session.board.is_game_over():
            self.status_var.set(self._game_over_text())
            return
        if self.session.is_human_turn:
            self.status_var.set("It is your move.")
            return
        self._thinking = True
        self.status_var.set("Engine thinking...")
        self.controller.request_move(self.session.board)

    def _schedule_engine_move(self) -> None:
        self._thinking = True
        self.status_var.set("Engine thinking...")
        self._engine_after_id = self.after(COMPUTER_REPLY_DELAY_MS, self._request_engine_move)

    def _request_engine_move(self) -> None:
        self._engine_after_id = None
        self.controller.request_move(self.session.board)

    def _cancel_engine(self) -> None:
        """Stop any scheduled or in-flight engine move so the position can change safely."""
        if self._engine_after_id is not None:
            self.after_cancel(self._engine_after_id)
            self._engine_after_id = None
        self.controller.cancel_pending()
        self._thinking = False

    def _poll_engine_results(self) -> None:
        for result in self.controller.get_pending_results():
            if result.request_id != self.controller.request_id:
                continue
            self._thinking = False
            if result.error:
                self.evaluation_bar.clear("!")
                self.status_var.set(f"Engine error: {result.error}")
                continue
            if result.kind == "analyse":
                self.evaluation_bar.set_score(result.score)
                self._best_move_hint = result.move
                continue
            if result.move is None:
                self.evaluation_bar.set_score(result.score)
                self.status_var.set("Engine did not return a move.")
                continue
            self.evaluation_bar.set_score(result.score)
            board_before = self.session.board.copy(stack=False)
            if not self.session.play_engine_move(result.move):
                self._audio.play_error()
                self.status_var.set("Engine returned an illegal move.")
                continue
            self._audio.play_move(board_before, result.move, self.session.board)
            self._refresh_board(animated_move=result.move)
            if self.session.board.is_game_over():
                self.status_var.set(self._game_over_text())
            else:
                self.status_var.set("Your move.")
                self._request_position_analysis()
        if self.winfo_exists():
            self.after(ENGINE_POLL_INTERVAL_MS, self._poll_engine_results)

    def _refresh_board(
        self,
        *,
        animated_move: chess.Move | None = None,
        snap: bool = False,
        animate: bool = True,
    ) -> None:
        if snap:
            self.board.set_position(self.session.board)
            self.board.set_last_move(None)
        else:
            self.board.advance_position(
                self.session.board,
                animated_move,
                clear_annotations=animated_move is not None,
                animate=animate,
            )

    def _request_position_analysis(self) -> None:
        if self.session.board.is_game_over():
            return
        self.evaluation_bar.clear("...")
        self.controller.request_analysis(self.session.board)

    def _game_over_text(self) -> str:
        outcome = self.session.board.outcome()
        if outcome is None:
            return "Game over."
        if outcome.winner is None:
            return "Game over: draw."
        return f"Game over: {'White' if outcome.winner == chess.WHITE else 'Black'} wins."
