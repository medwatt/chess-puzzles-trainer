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
)
from chess_puzzles.engine.board_analysis_frame import BoardAnalysisFrame
from chess_puzzles.engine.config import EngineDefinition
from chess_puzzles.engine.play_controller import EnginePlayController
from chess_puzzles.engine.play_session import EnginePlaySession
from chess_puzzles.platform.audio import AudioPlayer
from chess_puzzles.shortcuts import ENGINE_MOVE_KEY, PlayShortcuts
from chess_puzzles.ui.window import fit_window


class EnginePlayWindow(tk.Toplevel):
    """Free-play window where the user plays a position against the engine.

    Two ways to use it, chosen with the auto-reply checkbox. With it on the
    engine answers every move, which is what makes it a refutation board: you
    play the move you believed in and watch it punished. With it off nothing
    moves unless asked, so the same board becomes an exploration one -- you
    play both sides and call the engine when you want its opinion.
    """

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
        # Modeless work window: keep native minimize/maximize controls.
        self._presenter = presenter
        self._audio = audio
        self.session = EnginePlaySession(initial_board, human_color)
        self.controller = EnginePlayController(engine)
        self._thinking = False
        self._engine_after_id: str | None = None
        self._best_move_hint: chess.Move | None = None
        self._auto_reply_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar()

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
        for sequence, action in (
            (PlayShortcuts.ENGINE_MOVE, self.engine_move),
            (PlayShortcuts.TAKEBACK, self.takeback),
            (PlayShortcuts.RESET_POSITION, self.reset_position),
            (PlayShortcuts.SHOW_BEST_MOVE, self.show_best_move),
        ):
            self.bind(sequence, lambda _event, run=action: run())

        # Left: what you do, most-used first. Right: how the window behaves.
        # Closing is left to the title bar, as on any modeless window.
        controls = ttk.Frame(root)
        controls.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self._engine_move_button = ttk.Button(
            controls, text="Engine Move", command=self.engine_move, takefocus=False
        )
        self._engine_move_button.pack(side=tk.LEFT)
        ttk.Button(controls, text="Takeback", command=self.takeback, takefocus=False).pack(
            side=tk.LEFT, padx=(8, 0)
        )
        ttk.Button(
            controls, text="Reset Position", command=self.reset_position, takefocus=False
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Checkbutton(
            controls,
            text="Engine replies automatically",
            variable=self._auto_reply_var,
            command=self._on_auto_reply_changed,
            takefocus=False,
        ).pack(side=tk.RIGHT)

        ttk.Label(self, textvariable=self.status_var, anchor=tk.W, padding=(8, 3), relief=tk.SUNKEN).pack(
            fill=tk.X,
            side=tk.BOTTOM,
        )

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Destroy>", self._on_destroy)
        self._refresh_board(snap=True)
        self._continue_after_move()
        self.after(ENGINE_POLL_INTERVAL_MS, self._poll_engine_results)
        fit_window(self, PLAY_WINDOW_GEOMETRY)

    def reset_position(self) -> None:
        self.session.reset()
        self._cancel_engine()
        self._best_move_hint = None
        self.evaluation_bar.clear()
        self._refresh_board(snap=True)
        self._continue_after_move()
        if not self._thinking:
            self._set_status(f"Position reset. {self._turn_status()}")

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
            self._set_status("Illegal move.")
            return
        # Any accepted move (own or forced for the engine) invalidates scheduled
        # engine moves and in-flight analysis of the previous position.
        self._cancel_engine()
        self._audio.play_move(board_before, accepted, self.session.board)
        self._refresh_board(animated_move=accepted, animate=animate)
        hint = self._best_move_hint
        self._best_move_hint = None
        if hint is not None and hint != accepted:
            self._show_move_arrow(hint)
        self._continue_after_move()

    def takeback(self) -> None:
        if self.session.takeback() is None:
            self._set_status("Nothing to take back.")
            return
        self._cancel_engine()
        self._best_move_hint = None
        self._refresh_board(snap=True)
        self._continue_after_move()

    def _continue_after_move(self) -> None:
        """Whose turn it now is, and whether anything happens by itself.

        The engine only takes its turn unasked while auto-reply is on; the
        rest of the time the position simply sits there, analysed, waiting
        for whichever side the user wants to move.
        """
        if self.session.board.is_game_over():
            self._set_status(self._game_over_text())
            return
        if not self.session.is_human_turn and self._auto_reply_var.get():
            self._schedule_engine_move()
            return
        self._request_position_analysis()
        self._set_status(self._turn_status())

    def _turn_status(self) -> str:
        if self.session.is_human_turn:
            return "Your move."
        return f"Engine's turn - press {ENGINE_MOVE_KEY} for its move, or play it yourself."

    def _on_auto_reply_changed(self) -> None:
        """Switching it back on lets the engine catch up on the move it owes."""
        if not self._auto_reply_var.get():
            self._cancel_engine()
        self._continue_after_move()

    def show_best_move(self) -> None:
        move = self._best_move_hint
        if move is None or move not in self.session.board.legal_moves:
            self._set_status("No engine suggestion for this position yet.")
            return
        self._show_move_arrow(move)
        self._set_status(f"Engine suggests {self.session.board.san(move)}.")

    def _show_move_arrow(self, move: chess.Move) -> None:
        self.board.set_annotations(
            BoardAnnotations(
                arrows=(ArrowAnnotation(move.from_square, move.to_square, AnnotationColor.YELLOW),)
            )
        )

    def _set_status(self, text: str) -> None:
        """Every status change settles the Engine Move button too, so the
        button can never claim to be available when it is not."""
        self.status_var.set(text)
        self._engine_move_button.configure(
            state=tk.NORMAL if self._engine_can_move else tk.DISABLED
        )

    @property
    def _engine_can_move(self) -> bool:
        return (
            not self._thinking
            and not self.session.is_human_turn
            and not self.session.board.is_game_over()
        )

    def engine_move(self) -> None:
        # Reachable from the keyboard even when the button is disabled.
        if self._thinking:
            return  # already on its way, and the status already says so
        if not self._engine_can_move:
            self._set_status(
                self._game_over_text()
                if self.session.board.is_game_over()
                else "It is your move."
            )
            return
        self._begin_thinking()
        self.controller.request_move(self.session.board)

    def _schedule_engine_move(self) -> None:
        self._begin_thinking()
        self._engine_after_id = self.after(COMPUTER_REPLY_DELAY_MS, self._request_engine_move)

    def _begin_thinking(self) -> None:
        self._thinking = True
        self._set_status("Engine thinking...")

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
                self._set_status(f"Engine error: {result.error}")
                continue
            if result.kind == "analyse":
                self.evaluation_bar.set_score(result.score)
                self._best_move_hint = result.move
                continue
            if result.move is None:
                self.evaluation_bar.set_score(result.score)
                self._set_status("Engine did not return a move.")
                continue
            self.evaluation_bar.set_score(result.score)
            board_before = self.session.board.copy(stack=False)
            if not self.session.play_engine_move(result.move):
                self._audio.play_error()
                self._set_status("Engine returned an illegal move.")
                continue
            self._audio.play_move(board_before, result.move, self.session.board)
            self._refresh_board(animated_move=result.move)
            self._continue_after_move()
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
