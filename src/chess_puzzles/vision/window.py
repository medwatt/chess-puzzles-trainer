"""The board vision window -- a sibling of the Play vs Engine window.

It owns its own board and a VisionSession, translates board clicks into answers,
shows the solution as feedback, and records each trial. It never touches the
puzzle session in the main window.
"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

import chess

from chess_puzzles.board import (
    AnnotationColor,
    ArrowAnnotation,
    BoardAnnotations,
    BoardCapabilities,
    BoardPresenter,
    BoardView,
    PresentationPolicy,
)
from chess_puzzles.board.annotations import SquareAnnotation
from chess_puzzles.board.input import BoardEvent, SquareSelected
from chess_puzzles.constants import VISION_WINDOW_GEOMETRY, VISION_WINDOW_MINSIZE
from chess_puzzles.platform.audio import AudioPlayer
from chess_puzzles.store import UserStore, VisionAttempt, now_iso
from chess_puzzles.vision.drill import TrialResult, shows_coordinates
from chess_puzzles.vision import analysis
from chess_puzzles.vision.analysis import ColorScope
from chess_puzzles.vision.options_panel import OptionsPanel
from chess_puzzles.vision.registry import registry
from chess_puzzles.vision.session import VisionSession
from chess_puzzles.vision.settings import (
    TIMER_CHOICES,
    VisionSettings,
    load_vision_settings,
    save_vision_settings,
)
from chess_puzzles.vision.source import LichessCsvSource, PositionSource, PositionUnavailable

# A correct answer advances on its own quickly; a miss waits so the solution
# (shown in green) can be studied, then advances on Enter / the Next button.
_PASS_ADVANCE_MS = 900
_TICK_MS = 200
# Fixed sidebar width so per-drill option widgets can't reflow the board column
# (which would resize the board canvas when switching drills).
_SIDEBAR_WIDTH = 260
# Live HUD rows, in display order. The single source of truth for both building
# the panel and refreshing it.
_STAT_ROWS = ("Attempted", "Correct", "Accuracy", "Streak", "Avg time", "Total time")


def _timer_label(seconds: int) -> str:
    return "Untimed" if seconds == 0 else f"{seconds}s"


def _format_duration(ms: int) -> str:
    seconds = ms / 1000
    if seconds >= 60:
        return f"{int(seconds) // 60}m {int(seconds) % 60:02d}s"
    return f"{seconds:.1f}s"


class BoardVisionWindow(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        presenter: BoardPresenter,
        audio: AudioPlayer,
        user_store: UserStore,
        csv_path: str,
    ) -> None:
        super().__init__(parent, name="boardvision", class_="ChessPuzzlesBoardVision")
        self.title("Board Vision")
        self.minsize(*VISION_WINDOW_MINSIZE)
        self.geometry(VISION_WINDOW_GEOMETRY)
        # Modeless work window: keep native minimize/maximize controls.

        self._presenter = presenter
        self._audio = audio
        self._user_store = user_store
        self._csv_path = csv_path
        self._source: PositionSource | None = None
        self.session: VisionSession | None = None

        self._settings = load_vision_settings()
        self._board_size = 0  # last square size applied by _fit_board, to skip no-op resizes
        self._awaiting_feedback = False
        self._deadline: float | None = None
        self._timeout_after_id: str | None = None
        self._tick_after_id: str | None = None
        self._next_after_id: str | None = None

        self._drills = registry.all()
        self._names = [drill.name for drill in self._drills]
        self.status_var = tk.StringVar(value="Pick a drill and press Start.")
        self.prompt_var = tk.StringVar(value="")
        self.timer_var = tk.StringVar(value="")
        self._stat_vars = {key: tk.StringVar(value="-") for key in _STAT_ROWS}

        self._build_ui()

        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Destroy>", self._on_destroy)
        self.bind("<space>", lambda _event: self._primary_action())

    # UI ---------------------------------------------------------------
    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=(8, 8, 8, 0))
        root.pack(fill=tk.BOTH, expand=True)
        # Empty side columns (0 and 3) take all the slack, centring the board and
        # its sidebar as a group so they stay together however wide the window is.
        root.columnconfigure(0, weight=1)  # left spacer
        root.columnconfigure(3, weight=1)  # right spacer
        root.rowconfigure(1, weight=1)  # the board / sidebar row takes the height

        # Prompt banner on its own row, so the sidebar (row 1) lines up with the top
        # of the board rather than being pushed up above it.
        self._prompt = ttk.Label(
            root,
            textvariable=self.prompt_var,
            font=("TkDefaultFont", 20, "bold"),
            anchor=tk.CENTER,
            justify=tk.CENTER,
            wraplength=560,
        )
        self._prompt.grid(row=0, column=1, sticky="ew", pady=(0, 6))

        # The board is a square filling this row's height; its column then shrinks to
        # that width so the sidebar stays glued, and the spacer columns centre the
        # pair. We bind ``root`` (whose size the window fixes) rather than the board's
        # own container, so resizing the board can't perturb what we measure -- that
        # feedback is what made the board oscillate.
        board_outer = self._board_outer = ttk.Frame(root)
        board_outer.grid(row=1, column=1, sticky="nsew", padx=(0, 8), pady=(0, 8))
        board_outer.columnconfigure(0, weight=1)
        board_outer.rowconfigure(0, weight=1)

        self.board = BoardView(
            board_outer,
            capabilities=BoardCapabilities(
                movable_pieces=False, annotations=True, legal_move_hints=False, select_any_square=True
            ),
            event_handler=self._handle_board_event,
        )
        self.board.grid(row=0, column=0)
        self._presenter.register(self.board, PresentationPolicy(coordinates=False))
        # after_idle so the layout has settled before we measure (see _fit_board).
        root.bind("<Configure>", lambda _event: self.after_idle(self._fit_board))

        self._build_sidebar(root)

        status = ttk.Label(self, textvariable=self.status_var, anchor=tk.W, padding=(8, 3), relief=tk.SUNKEN)
        status.pack(fill=tk.X, side=tk.BOTTOM)

    def _fit_board(self) -> None:
        # Size the board to a square filling its row. We read board_outer's height,
        # which the board's own width can't change, so this can't feed back into a
        # resize loop; the guard skips redundant resizes during a live drag.
        size = max(1, self._board_outer.winfo_height())
        if size != self._board_size:
            self._board_size = size
            self.board.configure(width=size, height=size)

    def _build_sidebar(self, root: ttk.Frame) -> None:
        sidebar = ttk.Frame(root, padding=(0, 2, 0, 0), width=_SIDEBAR_WIDTH)
        sidebar.grid(row=1, column=2, sticky="nsew")
        sidebar.grid_propagate(False)  # keep the fixed width regardless of contents
        sidebar.columnconfigure(0, weight=1)

        controls = ttk.Frame(sidebar)
        controls.grid(row=0, column=0, sticky="ew")
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Type").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=2)
        initial = registry.get(self._settings.last_drill_id)
        self._drill_box = ttk.Combobox(controls, values=self._names, state="readonly", takefocus=False)
        self._drill_box.set(initial.name if initial is not None else self._names[0])
        self._drill_box.grid(row=0, column=1, sticky="ew", pady=2)
        self._drill_box.bind("<<ComboboxSelected>>", lambda _event: self._on_drill_changed())

        ttk.Label(controls, text="Timer").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=2)
        self._timer_box = ttk.Combobox(
            controls, values=[_timer_label(s) for s in TIMER_CHOICES], state="readonly", takefocus=False
        )
        self._timer_box.set(_timer_label(self._settings.timer_seconds))
        self._timer_box.grid(row=1, column=1, sticky="ew", pady=2)
        self._timer_box.bind("<<ComboboxSelected>>", lambda _event: self._on_settings_changed())

        # Per-drill options, rebuilt from the selected drill's OPTIONS declaration.
        self._options = OptionsPanel(sidebar)
        self._options.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self._options.show(self._selected_drill())

        buttons = ttk.Frame(sidebar)
        buttons.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self._start_button = ttk.Button(buttons, text="Start", command=self._toggle_session, takefocus=False)
        self._start_button.pack(side=tk.LEFT)
        self._submit_button = ttk.Button(
            buttons, text="Submit", command=self._primary_action, takefocus=False, state=tk.DISABLED
        )
        self._submit_button.pack(side=tk.RIGHT)

        ttk.Label(sidebar, textvariable=self.timer_var, anchor=tk.W).grid(row=3, column=0, sticky="ew", pady=(8, 0))

        stats = ttk.LabelFrame(sidebar, text="Session", padding=(8, 6))
        stats.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        stats.columnconfigure(1, weight=1)
        for row, key in enumerate(_STAT_ROWS):
            ttk.Label(stats, text=key).grid(row=row, column=0, sticky="w", padx=(0, 8))
            ttk.Label(stats, textvariable=self._stat_vars[key]).grid(row=row, column=1, sticky="w")

    # Session control --------------------------------------------------
    def _selected_drill(self):
        return self._drills[max(self._drill_box.current(), 0)]

    def _selected_timer_seconds(self) -> int:
        return TIMER_CHOICES[[_timer_label(s) for s in TIMER_CHOICES].index(self._timer_box.get())]

    def _on_settings_changed(self) -> None:
        self._settings = VisionSettings(
            last_drill_id=self._selected_drill().id, timer_seconds=self._selected_timer_seconds()
        )
        save_vision_settings(self._settings)

    def _on_drill_changed(self) -> None:
        self._on_settings_changed()
        self._options.show(self._selected_drill())

    def _toggle_session(self) -> None:
        if self.session is not None:
            self._stop_session()
        else:
            self._start_session()

    def _start_session(self) -> None:
        if self._source is None:
            try:
                self._source = LichessCsvSource(self._csv_path)
            except PositionUnavailable as exc:
                self.status_var.set(str(exc))
                return
        self._on_settings_changed()
        self.session = VisionSession(self._options.configured(self._selected_drill()), self._source)
        self._refresh_stats()
        self._start_button.configure(text="Stop")
        self._drill_box.configure(state=tk.DISABLED)
        self._options.set_enabled(False)
        self._next_question()

    def _stop_session(self) -> None:
        self._cancel_timers()
        self.session = None
        self._awaiting_feedback = False
        self._start_button.configure(text="Start")
        self._drill_box.configure(state="readonly")
        self._options.set_enabled(True)
        self._submit_button.configure(text="Submit", state=tk.DISABLED)
        self.prompt_var.set("")
        self.timer_var.set("")
        self.board.clear_annotations()
        self.status_var.set("Stopped. Press Start to run again.")

    def _next_question(self) -> None:
        if self.session is None:
            return
        self._cancel_timers()
        try:
            question = self.session.next_question()
        except PositionUnavailable as exc:
            self.status_var.set(f"{exc} Try another drill.")
            self._stop_session()
            return
        self._awaiting_feedback = False
        self.board.set_position(question.fen)
        self.board.set_orientation(question.orientation)
        # Some drills (localization) must hide coordinates; otherwise follow the
        # app-wide setting carried by the shared presenter.
        drill_allows = shows_coordinates(self.session.drill)
        self.board.set_coordinates_visible(drill_allows and self._presenter.presentation.show_coordinates)
        self._render_selection()
        self.prompt_var.set(question.prompt)
        self._submit_button.configure(
            text="Submit", state=tk.DISABLED if self.session.is_single_click else tk.NORMAL
        )
        side = "White" if chess.Board(question.fen).turn else "Black"
        action = "Click your answer." if self.session.is_single_click else "Click squares, then Submit."
        self.status_var.set(f"{side} to move. {action}")
        self.board.focus_set()  # keep Space bound to the window, not a sidebar widget
        self._start_timer()

    # Board events -----------------------------------------------------
    def _handle_board_event(self, event: BoardEvent) -> None:
        if not isinstance(event, SquareSelected) or event.square is None:
            return
        if self.session is None or self.session.question is None or self._awaiting_feedback:
            return
        self.session.toggle(event.square)
        self._render_selection()
        if self.session.is_single_click:
            self._submit()

    def _render_selection(self) -> None:
        if self.session is None or self.session.question is None:
            return
        squares = [SquareAnnotation(sq, AnnotationColor.BLUE) for sq in self.session.question.highlight]
        squares += [SquareAnnotation(sq, AnnotationColor.GREEN) for sq in self.session.clicks]
        self.board.set_annotations(BoardAnnotations(squares=tuple(squares)))

    def _primary_action(self) -> None:
        """The Submit button / Space: grade an answer, or advance after a miss."""
        if self._awaiting_feedback:
            self._next_question()
        elif self.session is not None and self.session.question is not None:
            self._submit()

    def _submit(self) -> None:
        if self.session is None or self.session.question is None or self._awaiting_feedback:
            return
        self._cancel_timers()
        self._awaiting_feedback = True
        result = self.session.submit()
        self._record(result)
        self._show_solution(result)
        self._refresh_stats()
        self.timer_var.set("")
        if result.passed:
            # A passed empty-answer trial means the user correctly judged the board
            # clean; say so, or it reads like a no-op that graded itself.
            empty = self.session.question is not None and not self.session.question.answer
            self.status_var.set("Correct -- nothing to find." if empty else "Correct!")
            self._submit_button.configure(state=tk.DISABLED)
            self._next_after_id = self.after(_PASS_ADVANCE_MS, self._next_question)
        else:
            self._audio.play_error()
            self.status_var.set(
                f"Missed {len(result.missed)}, wrong {len(result.wrong)}. "
                "Green = answer. Press Space / Next."
            )
            self._submit_button.configure(text="Next", state=tk.NORMAL)

    def _show_solution(self, result: TrialResult) -> None:
        # Keep the subject piece highlighted (blue) so the answer stays anchored to
        # it; show the full correct answer in green and the user's wrong clicks in red.
        question = self.session.question if self.session is not None else None
        if question is None:
            return
        squares = [SquareAnnotation(sq, AnnotationColor.BLUE) for sq in question.highlight]
        squares += [SquareAnnotation(sq, AnnotationColor.GREEN) for sq in question.answer]
        squares += [SquareAnnotation(sq, AnnotationColor.RED) for sq in result.wrong]
        arrows = self._feedback_arrows()
        self.board.set_annotations(BoardAnnotations(squares=tuple(squares), arrows=tuple(arrows)))

    def _feedback_arrows(self) -> list[ArrowAnnotation]:
        if self.session is None or self.session.question is None:
            return []
        drill = self.session.drill
        if drill.id != "long-range":
            return []
        board = chess.Board(self.session.question.fen)
        scope = getattr(drill, "scope", ColorScope.SIDE_TO_MOVE)
        include_pawns = getattr(drill, "include_pawns", False)
        targets = analysis.long_range_attack_targets(board, scope=scope, include_pawns=include_pawns)
        arrows: list[ArrowAnnotation] = []
        for origin, target_squares in targets.items():
            for target in target_squares:
                arrows.append(ArrowAnnotation(origin, target, AnnotationColor.YELLOW))
        return arrows

    def _record(self, result: TrialResult) -> None:
        question = self.session.question if self.session is not None else None
        if question is None:
            return
        self._user_store.record_vision_attempt(
            VisionAttempt(
                drill_id=self.session.drill.id,
                at=now_iso(),
                fen=question.fen,
                orientation=int(question.orientation),
                answer=",".join(str(sq) for sq in sorted(question.answer)),
                clicks=",".join(str(sq) for sq in sorted(self.session.clicks)),
                tp=len(result.correct),
                fp=len(result.wrong),
                fn=len(result.missed),
                passed=result.passed,
                elapsed_ms=result.elapsed_ms,
            )
        )

    def _refresh_stats(self) -> None:
        if self.session is None:
            return
        stats = self.session.stats
        has_trials = stats.trials > 0
        self._stat_vars["Attempted"].set(str(stats.trials))
        self._stat_vars["Correct"].set(str(stats.passed))
        self._stat_vars["Accuracy"].set(f"{stats.accuracy:.0f}%" if has_trials else "-")
        self._stat_vars["Streak"].set(str(stats.streak))
        self._stat_vars["Avg time"].set(f"{stats.average_ms / 1000:.1f}s" if has_trials else "-")
        self._stat_vars["Total time"].set(_format_duration(stats.total_ms) if has_trials else "-")

    # Timer ------------------------------------------------------------
    def _start_timer(self) -> None:
        seconds = self._selected_timer_seconds()
        if seconds == 0:
            self.timer_var.set("Untimed")
            return
        self._deadline = time.monotonic() + seconds
        self._timeout_after_id = self.after(seconds * 1000, self._on_timeout)
        self._tick()

    def _tick(self) -> None:
        if self._deadline is None:
            return
        remaining = max(0.0, self._deadline - time.monotonic())
        self.timer_var.set(f"Time: {remaining:.1f}s")
        if remaining > 0:
            self._tick_after_id = self.after(_TICK_MS, self._tick)

    def _on_timeout(self) -> None:
        self._timeout_after_id = None
        self.status_var.set("Time!")
        self._submit()

    def _cancel_timers(self) -> None:
        for attr in ("_timeout_after_id", "_tick_after_id", "_next_after_id"):
            after_id = getattr(self, attr)
            if after_id is not None:
                self.after_cancel(after_id)
                setattr(self, attr, None)
        self._deadline = None

    # Lifecycle --------------------------------------------------------
    def close(self) -> None:
        self._cancel_timers()
        self.destroy()

    def _on_destroy(self, event: tk.Event) -> None:
        if event.widget is self:
            self._presenter.unregister(self.board)
