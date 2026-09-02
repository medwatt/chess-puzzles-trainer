# imports <<<
from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path
from typing import Any
import tkinter as tk
from tkinter import filedialog, font, messagebox, simpledialog

import chess

from chess_puzzles.app.app_state import AppState
from chess_puzzles.app.info_display import HIDDEN_TEXT, info_display_for
from chess_puzzles.app.main_database_actions import MainDatabaseActions
from chess_puzzles.app.main_layout import MainLayoutBuilder
from chess_puzzles.app.main_menu import MainMenuBuilder
from chess_puzzles.app.main_user_notes import MainUserNotes
from chess_puzzles.app.variation_playback import VariationPlayback
from chess_puzzles.board import BoardPresentation, BoardPresenter, snapshot_to_svg
from chess_puzzles.board.board_state import BoardSnapshot
from chess_puzzles.board.board_theme import PieceTheme, default_annotation_theme
from chess_puzzles.board.control import ControlOverlayMode
from chess_puzzles.constants import (
    AUTO_NEXT_DELAY_MS,
    COMPUTER_REPLY_DELAY_MS,
    DEFAULT_BOARD_THEME_ID,
    DEFAULT_PIECE_THEME_ID,
    ENGINE_POLL_INTERVAL_MS,
    FLASH_CORRECT_COLOR,
    MAIN_WINDOW_MINSIZE,
    PREFIX_RECAP_STEP_DELAY_MS,
)
from chess_puzzles.board.input import BoardEvent, MoveRequested
from chess_puzzles.dialogs.choice import ChoiceDialog
from chess_puzzles.dialogs.paths import PathField, PathsDialog
from chess_puzzles.dialogs.font import FontChooserDialog
from chess_puzzles.dialogs.shortcuts_help import ShortcutsHelpDialog
from chess_puzzles.dialogs.statistics import StatisticsDialog
from chess_puzzles.engine import EngineController, EngineState
from chess_puzzles.engine.config import EngineConfig, load_engine_config, save_engine_config
from chess_puzzles.engine.dialogs import EngineConfigDialog
from chess_puzzles.engine.play_window import EnginePlayWindow
from chess_puzzles.vision.window import BoardVisionWindow
from chess_puzzles.platform.audio import AudioPlayer
from chess_puzzles.pgn import PgnLoader
from chess_puzzles.pgn.comments import strip_annotation_commands
from chess_puzzles.pgn.exporter import export_puzzles_to_pgn
from chess_puzzles.pgn.utils import pgn_for_puzzle
from chess_puzzles.pgn.viewer import PgnViewer
from chess_puzzles.puzzle import MoveResult, Puzzle, PuzzleSession, MistakeLine
from chess_puzzles.puzzle.grade import grade_solve
from chess_puzzles.puzzle.prefix import drill_prefix_length
from chess_puzzles.reports import AttemptSummary, attempt_summary, format_duration_ms
from chess_puzzles.dialogs.options import OptionsDialog
from chess_puzzles.settings.options import OPTIONS, QUICK_OPTIONS
from chess_puzzles.settings.repository import SettingsRepository
from chess_puzzles.shortcuts import CONTINUE_KEY
from chess_puzzles.store import (
    DECK_KIND_ARENA,
    DECK_KIND_REPERTOIRE,
    Attempt,
    ContentDatabase,
    FavoriteRef,
    UserStore,
    now_iso,
)
from chess_puzzles.arena import puzzle_rating_of, read_arena_config, refill, session_rating
from chess_puzzles.settings.theme_repository import (
    UiTheme,
    available_piece_themes,
    built_in_board_themes,
)
from chess_puzzles.text_utils import display_comment
from chess_puzzles.ui.theme import ThemeService
# >>>


class MainWindow:
    def __init__(
        self,
        root: tk.Tk,
        *,
        state: AppState,
        settings_repository: SettingsRepository,
        theme_service: ThemeService,
    ) -> None:
        # Injected dependencies
        self.root = root
        self.state = state
        self.settings_repository = settings_repository
        self.theme_service = theme_service

        # Theme catalogues and the tk vars bound to the Settings menu radios
        self.board_themes = built_in_board_themes()
        self.piece_themes = available_piece_themes(state.settings.piece_assets_directory)
        self._ui_theme_var = tk.StringVar(value=state.settings.ui_theme_id)
        self._board_theme_var = tk.StringVar(value=state.settings.board_theme_id)
        self._piece_theme_var = tk.StringVar(value=state.settings.piece_theme_id)

        # Preferences live in state.settings and are read through option();
        # only the sidebar's quick toggles need a tk variable, kept in step
        # by set_option. See settings.options for the full table.
        self._quick_vars: dict[str, tk.BooleanVar] = {
            option.key: tk.BooleanVar(value=bool(getattr(state.settings, option.key)))
            for option in QUICK_OPTIONS
        }
        # Not a preference: it edits the open puzzle's skip flag.
        self._skip_first_var = tk.BooleanVar(value=False)

        # Sidebar/status text bound to labels
        self._status_var = tk.StringVar(value="Ready")
        self._title_var = tk.StringVar(value="No puzzle loaded")
        self._info_vars: dict[str, tk.StringVar] = {
            key: tk.StringVar(value="-")
            for key in ("Puzzle", "Move", "Turn", "Side", "Start", "Theme")
        }
        self._session_stats_vars: dict[str, tk.StringVar] = {
            key: tk.StringVar(value="-") for key in ("Attempted", "Solved", "Total", "Average")
        }
        self._move_progress = tk.DoubleVar(value=0.0)

        # Loaded puzzle data and the currently active session
        self.current_index = -1
        self.session: PuzzleSession | None = None
        self.database: ContentDatabase | None = None
        self.database_path: Path | None = None
        self.favorites_view = False
        # A favorites-style list view serving the review queue: the favorite
        # button toggles against the puzzle's source deck instead of removing
        # the puzzle from the list.
        self.review_view = False
        self.favorite_sources: list[FavoriteRef] = []
        self.active_theme = ""

        # Private user store + per-visit attempt tracking (see _record_solve)
        self.user_store = UserStore.open_default()
        # Session stats count attempts since this anchor; "Reset" moves it to now.
        self._stats_anchor = now_iso()
        self._engaged = False
        self._line_demonstrated = False
        self._visit_recorded = False
        self._solve_clock_start: float | None = None
        # Mistakes/aids from earlier runs of this visit: PuzzleSession.reset()
        # zeroes its counters, but the recorded attempt must keep the evidence
        # (mistake -> reset -> clean finish is not a flawless solve).
        self._carry_mistakes = 0
        self._carry_aids = 0
        # Cached arena session rating (recomputed on load and after attempts;
        # the fold itself lives in arena.rating and derives from the log).
        self._arena_rating: float | None = None

        # Engine config and analysis controller
        self.engine_config: EngineConfig = load_engine_config()
        self.engine_controller = EngineController(self.engine_config)

        # Computer-reply scheduling (within the current session)
        self._computer_reply_after_id: str | None = None
        self._prefix_after_id: str | None = None
        self.waiting_for_continue = False
        self._playback = VariationPlayback(self)
        # Post-solve coda: marked mistakes the user walked past, offered for
        # review after completion. _seen_mistakes keys (decision FEN, move
        # uci) the user already experienced this puzzle, so a mistake they
        # played is not re-offered as a lesson.
        self._avoided_mistakes: list[tuple[str, MistakeLine]] = []
        self._seen_mistakes: set[tuple[str, str]] = set()

        # Engine result polling runs only while analysis is active.
        # Continuous evaluation only happens when the user asked for it;
        # an engine auto-started by a threat query must not feed the eval bar.
        self._engine_poll_after_id: str | None = None
        self._analysis_user_enabled = False

        # Lazily-created child windows
        self._pgn_viewer: PgnViewer | None = None
        self._engine_play_window: EnginePlayWindow | None = None
        self._board_vision_window: BoardVisionWindow | None = None
        self._shortcuts_dialog: ShortcutsHelpDialog | None = None

        # Shared subsystems used by helpers
        self.loader = PgnLoader()
        self.audio = AudioPlayer(enabled=state.settings.sound_enabled)
        self.presenter = BoardPresenter(self._build_initial_presentation())

        # Top-level window setup
        self.root.title("Chess Puzzles Trainer")
        self.root.minsize(*MAIN_WINDOW_MINSIZE)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        # Helper subsystems (each builds part of the window in its __init__)
        self._database = MainDatabaseActions(self)
        self._user_notes = MainUserNotes(self)
        self._menu = MainMenuBuilder(self)
        self._layout = MainLayoutBuilder(self)

        # Final wiring after the UI exists
        self._apply_font_settings()
        self.theme_service.add_listener(self._apply_theme)
        self._update_analysis_button_label()
        self._refresh_session_stats()

    def set_ui_theme(self, theme_id: str, *, persist: bool = True) -> None:
        theme = self.theme_service.apply(theme_id)
        self._ui_theme_var.set(theme.id)
        if persist:
            self.save_settings(ui_theme_id=theme.id)
        self._status_var.set(f"Application theme: {theme.name}")

    def set_board_theme(self, theme_id: str, *, persist: bool = True) -> None:
        theme = self.board_themes.get(theme_id, self.board_themes[DEFAULT_BOARD_THEME_ID])
        self._board_theme_var.set(theme.id)
        self.presenter.update(board_theme=theme)
        if persist:
            self.save_settings(board_theme_id=theme.id)
        self._status_var.set(f"Board theme: {theme.name}")

    def set_piece_theme(self, theme_id: str, *, persist: bool = True) -> None:
        theme = self._piece_theme_or_default(theme_id)
        self._piece_theme_var.set(theme.id)
        self.presenter.update(piece_theme=theme)
        if persist:
            self.save_settings(piece_theme_id=theme.id)
        self._status_var.set(f"Piece theme: {theme.name}")

    def flip_board(self) -> None:
        self._layout.board.set_flipped(not self._layout.board.state.flipped)

    def clear_marks(self) -> None:
        self._layout.board.clear_annotations()

    def reset_position(self) -> None:
        """Restart the board without erasing evidence from this visit.

        This is deliberately uniform across tactics, repertoire, reviews, and
        rated sessions: Reset is a way to replay the position, not a way to
        turn a mistaken or assisted attempt into a clean one. PuzzleSession's
        per-run counters reset; the carried counters are persisted when the
        visit is eventually recorded.
        """
        if self.session is None:
            self._layout.board.set_position(chess.Board())
            self._layout.board.set_last_move(None)
            self._status_var.set("Position reset")
            return
        self.cancel_computer_reply()
        self.cancel_prefix_recap()
        self._playback.cancel()
        # _seen_mistakes survives a reset on purpose: a mistake already
        # experienced this visit is not re-offered after re-solving.
        self._avoided_mistakes = []
        # The run's counters restart, but the visit's evidence must not.
        self._carry_mistakes += self.session.mistakes
        self._carry_aids += self.session.aids_used
        self.session.reset()
        self._refresh_from_session("Puzzle reset.")
        if self.session.in_prefix:
            self._start_prefix_recap()
        else:
            self._schedule_computer_reply()

    def close(self) -> None:
        try:
            self._user_notes.save_now()
            self._finalize_visit()
            self.user_store.close()
            self.engine_controller.shutdown()
            self.audio.close()
            self.settings_repository.save(self.state.settings)
        finally:
            self.root.destroy()

    def clear_recent_databases(self) -> None:
        self.save_settings(recent_database_paths=())
        self._menu.refresh_recent_menu()
        self._status_var.set("Recent files cleared")

    def copy_current_position(self) -> None:
        fen = (
            self.session.board.fen()
            if self.session is not None
            else self._layout.board.state.board.fen()
        )
        self.root.clipboard_clear()
        self.root.clipboard_append(fen)
        self._status_var.set("Current FEN copied")

    def copy_current_pgn(self) -> None:
        if self.session is None:
            self._status_var.set("No puzzle loaded")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(pgn_for_puzzle(self.session.puzzle))
        self._status_var.set("Puzzle PGN copied")

    def toggle_current_skip(self) -> None:
        if self.session is None or self.database is None:
            return
        if self.arena_mode:
            self._status_var.set("Rated-session puzzles cannot be edited.")
            return
        value = not self.session.puzzle.skip_first_move
        self.database.set_skip_first_move(self.current_index + 1, value)
        self.load_current_puzzle()

    # --- preferences ----------------------------------------------------
    # Every preference is read here and nowhere else, so a row in
    # settings.options is all a new one needs. _apply_option holds the few
    # that change the window the moment they are set.

    def option(self, key: str) -> Any:
        return getattr(self.state.settings, key)

    def set_option(self, key: str, value: object) -> None:
        self.save_settings(**{key: value})
        variable = self._quick_vars.get(key)
        if variable is not None:
            variable.set(bool(value))
        self._apply_option(key)

    def toggle_option(self, key: str) -> None:
        self.set_option(key, not bool(self.option(key)))

    def configure_options(self) -> None:
        values = {option.key: self.option(option.key) for option in OPTIONS}
        deck_kind = self.database.kind if self.database is not None else None
        result = OptionsDialog(self.root, values, deck_kind=deck_kind).show_modal()
        if result is None:
            return
        for key, value in result.items():
            if value != values[key]:
                self.set_option(key, value)
        self._status_var.set("Options saved.")

    def _apply_option(self, key: str) -> None:
        """Show the change now, for the preferences the window can act on."""
        if key == "show_coordinates":
            shown = bool(self.option(key))
            self.presenter.update(show_coordinates=shown)
            self._status_var.set("Coordinates shown" if shown else "Coordinates hidden")
        elif key == "show_evaluation_bar":
            self._layout.board_frame.set_evaluation_bar_visible(bool(self.option(key)))
        elif key == "show_session_stats":
            visible = bool(self.option(key))
            self._layout.set_session_stats_visible(visible)
            if visible:
                self._refresh_session_stats()
        elif key == "show_user_notes":
            self._user_notes.apply_visibility()
        elif key == "sound_enabled":
            self.audio.set_enabled(bool(self.option(key)))
        elif key == "reflow_comments":
            self._refresh_comment_view()
        elif key == "start_lines_at_divergence" and self._repertoire_deck:
            # Re-enter the current line under the new policy right away.
            self.load_current_puzzle()

    @property
    def _repertoire_deck(self) -> bool:
        return self.database is not None and self.database.kind == DECK_KIND_REPERTOIRE

    def _refresh_comment_view(self) -> None:
        if self.session is None or not hasattr(self._layout, "comment_view"):
            return
        self._replace_text(
            self._layout.comment_view, self._display_comment(self.session.current_comment)
        )

    def on_user_note_changed(self) -> None:
        self._user_notes.on_changed()

    def show_shortcuts_help(self) -> None:
        if self._shortcuts_dialog is not None and self._shortcuts_dialog.winfo_exists():
            self._shortcuts_dialog.lift()
            return
        self._shortcuts_dialog = ShortcutsHelpDialog(self.root, self.theme_service.current)

    def show_about(self) -> None:
        messagebox.showinfo(
            "About Chess-Puzzles-Trainer",
            "Chess-Puzzles-Trainer\n\n"
            "A desktop trainer for creating and solving chess puzzle databases from PGN files.\n\n"
            "Created by Mohamed Watfa.",
        )

    def _apply_theme(self, theme: UiTheme) -> None:
        self.root.configure(bg=theme.window_bg)
        self.presenter.update(surround_background=theme.window_bg)
        self._layout.refresh_button_icons()
        self._layout.apply_tooltip_theme()

    def _build_initial_presentation(self) -> BoardPresentation:
        settings = self.state.settings
        board_theme = self.board_themes.get(
            settings.board_theme_id, self.board_themes[DEFAULT_BOARD_THEME_ID]
        )
        piece_theme = self._piece_theme_or_default(settings.piece_theme_id)
        return BoardPresentation(
            board_theme=board_theme,
            piece_theme=piece_theme,
            annotation_theme=default_annotation_theme(),
            surround_background=self.theme_service.current.window_bg,
            show_coordinates=settings.show_coordinates,
        )

    def _apply_font_settings(self) -> None:
        settings = self.state.settings
        if not settings.font_family:
            return
        weight = "bold" if "bold" in settings.font_style else "normal"
        slant = "italic" if "italic" in settings.font_style else "roman"
        for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
            try:
                tk_font = font.nametofont(name)
            except tk.TclError:
                continue
            tk_font.configure(
                family=settings.font_family, size=settings.font_size, weight=weight, slant=slant
            )

    def _handle_board_event(self, event: BoardEvent) -> None:
        if isinstance(event, MoveRequested):
            self.on_move_requested(event.move, animate=event.animate)

    def export_board_svg(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export board SVG",
            defaultextension=".svg",
            filetypes=(("SVG files", "*.svg"), ("All files", "*.*")),
        )
        if not path:
            return
        snapshot = self._layout.board.snapshot_for_export()
        if snapshot.state.piece_theme.svg_directory is None:
            vector_theme = self._vector_piece_theme()
            if vector_theme is not None:
                snapshot = BoardSnapshot(
                    state=snapshot.state.copy_with(piece_theme=vector_theme),
                    width=snapshot.width,
                    height=snapshot.height,
                )
        svg = snapshot_to_svg(snapshot)
        try:
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(svg)
        except OSError as exc:
            messagebox.showerror("Export board SVG", f"Could not write SVG file:\n{exc}")
            return
        self._status_var.set(f"Board SVG exported: {path}")

    def _vector_piece_theme(self):
        for theme in self.piece_themes.values():
            if theme.svg_directory is not None:
                return theme
        return None

    def _piece_theme_or_default(self, theme_id: str) -> PieceTheme:
        return (
            self.piece_themes.get(theme_id)
            or self.piece_themes.get(DEFAULT_PIECE_THEME_ID)
            or next(iter(self.piece_themes.values()))
        )

    def save_settings(self, **changes: object) -> None:
        self.state.settings = replace(self.state.settings, **changes)
        self.settings_repository.save(self.state.settings)

    def _replace_text(self, widget: tk.Text, text: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.configure(state=tk.DISABLED)

    def _display_comment(self, comment: str) -> str:
        # [%csl]/[%cal] commands are board-drawing instructions, never prose,
        # so they are stripped regardless of the "Clean comments" toggle.
        return display_comment(strip_annotation_commands(comment), self.option("reflow_comments"))

    def edit_current_database(self) -> None:
        self._database.edit_current_database()

    def start_theme(self) -> None:
        if self.database is None:
            self._status_var.set("No database loaded")
            return
        themes = self.database.themes()
        if not themes:
            messagebox.showinfo("Start theme", "This database has no themes.", parent=self.root)
            return
        theme = ChoiceDialog(
            self.root, "Start theme", "Theme:", themes, self.active_theme or themes[0]
        ).show_modal()
        if theme is None:
            return
        self.active_theme = theme
        for index, puzzle in enumerate(self.database.iter_puzzles()):
            if puzzle.theme == theme:
                self.current_index = index
                self.load_current_puzzle()
                self._status_var.set(f"Started theme: {theme}")
                return

    def configure_paths(self) -> None:
        settings = self.state.settings
        fields = (
            PathField(
                key="default_database_directory",
                label="Database folder",
                description=(
                    "The Course Library scans this folder and its subfolders. "
                    "Database file dialogs also start here."
                ),
                value=settings.default_database_directory or "",
            ),
            PathField(
                key="piece_assets_directory",
                label="Custom pieces folder",
                description=(
                    "Extra piece sets, one sub-folder per set with sprite sheets named "
                    "<set>_<size>.png. A set named like a bundled one replaces it."
                ),
                value=settings.piece_assets_directory or "",
            ),
            PathField(
                key="lichess_csv_path",
                label="Lichess puzzle CSV",
                description=(
                    "The lichess.org puzzle database (CSV). Used by the CSV import, "
                    "rated sessions, board vision, and the blunder generator."
                ),
                value=settings.lichess_csv_path or "",
                kind="file",
                filetypes=(("CSV files", "*.csv"), ("All files", "*")),
            ),
        )
        result = PathsDialog(self.root, fields).show_modal()
        if result is None:
            return
        self.save_settings(
            default_database_directory=result["default_database_directory"] or None,
            piece_assets_directory=result["piece_assets_directory"] or None,
            lichess_csv_path=result["lichess_csv_path"] or None,
        )
        database_folder = self.state.settings.default_database_directory
        if database_folder:
            self.user_store.library.set_root(database_folder)
        self._reload_piece_themes()
        self._status_var.set("Paths updated.")

    def require_lichess_csv(self) -> str | None:
        """The configured Lichess CSV, or None after guiding the user to set it.

        The single gate every CSV-consuming feature goes through, so the
        path is only ever configured in Settings > Paths."""
        path = self.state.settings.lichess_csv_path
        if path and Path(path).is_file():
            return path
        if messagebox.askyesno(
            "Lichess CSV needed",
            "This feature reads the Lichess puzzle CSV, which is not configured yet."
            " Choose it now in Settings > Paths?",
            parent=self.root,
        ):
            self.configure_paths()
            path = self.state.settings.lichess_csv_path
            if path and Path(path).is_file():
                return path
        return None

    def _reload_piece_themes(self) -> None:
        self.piece_themes = available_piece_themes(self.state.settings.piece_assets_directory)
        self._menu.refresh_piece_theme_menu()
        # Re-resolve the saved theme id against the new catalogue without
        # persisting the fallback, so the choice survives a folder that is
        # temporarily unavailable.
        self.set_piece_theme(self.state.settings.piece_theme_id, persist=False)

    def choose_font(self) -> None:
        result = FontChooserDialog(self.root, self.state.settings).show_modal()
        if result is None:
            return
        family, style, size = result
        self.save_settings(font_family=family, font_style=style, font_size=size)
        self._apply_font_settings()
        self._status_var.set(f"Font set to {family} {size}.")

    def configure_engines(self) -> None:
        result = EngineConfigDialog(self.root, self.engine_config).show_modal()
        if result is None:
            return
        self.engine_config = result
        try:
            save_engine_config(result)
        except Exception as exc:
            messagebox.showerror("Could not save engines", str(exc), parent=self.root)
            return
        self.engine_controller.set_config(result)
        self._analysis_user_enabled = False
        self._layout.evaluation_bar.clear()
        self._status_var.set("Engine configuration saved.")
        self._update_analysis_button_label()

    def toggle_engine_analysis(self) -> None:
        if self._analysis_user_enabled:
            self._analysis_user_enabled = False
            self.engine_controller.pause()
            self._layout.evaluation_bar.clear()
            self._status_var.set("Engine analysis paused.")
            self._update_analysis_button_label()
            return
        if self.engine_controller.state != EngineState.RUNNING:
            error = self.engine_controller.start()
            if error:
                messagebox.showerror("Engine unavailable", error, parent=self.root)
                self._update_analysis_button_label()
                return
        self._analysis_user_enabled = True
        self._layout.evaluation_bar.clear("...")
        self._status_var.set("Engine analysis started.")
        self.engine_controller.analyse_if_running(self._current_analysis_board())
        self._update_analysis_button_label()
        self._ensure_engine_polling()

    def open_engine_play_window(self) -> None:
        engine = self.engine_config.default_engine
        if engine is None:
            messagebox.showerror(
                "Play vs Engine", "Configure a default engine first.", parent=self.root
            )
            return
        if self._engine_play_window is not None and self._engine_play_window.winfo_exists():
            self._engine_play_window.lift()
            return
        if self.session is not None:
            start_board = self.session.board.copy(stack=False)
            human_color = start_board.turn
            title = self.session.puzzle.title
        else:
            start_board = self._layout.board.state.board.copy(stack=False)
            human_color = start_board.turn
            title = "Free play"
        self._engine_play_window = EnginePlayWindow(
            self.root,
            start_board,
            human_color,
            engine,
            presenter=self.presenter,
            audio=self.audio,
            title=title,
            evaluation_bar_visible=self.state.settings.show_evaluation_bar,
        )

    def open_board_vision_window(self) -> None:
        if self._board_vision_window is not None and self._board_vision_window.winfo_exists():
            self._board_vision_window.lift()
            return
        csv_path = self.require_lichess_csv()
        if csv_path is None:
            return
        self._board_vision_window = BoardVisionWindow(
            self.root,
            presenter=self.presenter,
            audio=self.audio,
            user_store=self.user_store,
            csv_path=csv_path,
        )

    def _ensure_engine_polling(self) -> None:
        if self._engine_poll_after_id is None:
            self._engine_poll_after_id = self.root.after(
                ENGINE_POLL_INTERVAL_MS, self._poll_engine_results
            )

    def _poll_engine_results(self) -> None:
        self._engine_poll_after_id = None
        for result in self.engine_controller.get_pending_results():
            if result.analysis_id != self.engine_controller.analysis_id:
                continue
            if result.error:
                self.engine_controller.state = EngineState.ERROR
                self._layout.evaluation_bar.clear("!")
                self._status_var.set(f"Engine error: {result.error}")
                self._update_analysis_button_label()
                continue
            if result.purpose == "threat":
                self._show_threat_result(result.best_move)
                continue
            self._layout.evaluation_bar.set_score(result.score)
            if result.best_move is not None and result.score is not None:
                detail = f", depth {result.depth}" if result.depth is not None else ""
                self._status_var.set(f"Engine: {result.score.label}{detail}.")
        if self.engine_controller.state == EngineState.RUNNING:
            self._ensure_engine_polling()

    def _current_analysis_board(self) -> chess.Board | None:
        if self.session is not None:
            return self.session.board
        return self._layout.board.state.board

    def _request_engine_analysis(self) -> None:
        if not self._analysis_user_enabled or self.engine_controller.state != EngineState.RUNNING:
            return
        self._layout.evaluation_bar.clear("...")
        self.engine_controller.analyse_if_running(self._current_analysis_board())
        self._ensure_engine_polling()

    def _update_analysis_button_label(self) -> None:
        running = (
            self.engine_controller.state == EngineState.RUNNING and self._analysis_user_enabled
        )
        icon_name = "analysis_pause.png" if running else "analysis_start.png"
        text = "Pause Analysis" if running else "Start Analysis"
        self._layout.set_toolbar_button_icon(self._layout.toggle_analysis_button, icon_name, text)

    def create_database_from_pgn(self) -> None:
        self._user_notes.save_now()
        self._database.create_database_from_pgn()

    def add_course(self) -> None:
        self._user_notes.save_now()
        self._database.add_course()

    def open_database(self, database_path: Path | None = None) -> None:
        self._user_notes.save_now()
        self._database.open_database(database_path)

    def open_most_recent_course(self) -> None:
        self._user_notes.save_now()
        self._database.open_most_recent_course()

    def open_course_library(self) -> None:
        self._user_notes.save_now()
        self._database.open_course_library()

    def import_opening_course(self) -> None:
        self._user_notes.save_now()
        self._database.import_opening_course()

    def import_lichess_csv(self) -> None:
        self._user_notes.save_now()
        self._database.import_lichess_csv()

    def generate_blunder_puzzles(self) -> None:
        self._user_notes.save_now()
        self._database.generate_blunder_puzzles()

    def load_current_puzzle(self) -> None:
        self._finalize_visit()
        if (
            self.database is None
            or self.current_index < 0
            or self.current_index >= self.database.count()
        ):
            return
        puzzle = self.database.puzzle_at(self.current_index)
        player_color = self._player_color_for_puzzle(puzzle)
        self.cancel_prefix_recap()
        self.session = PuzzleSession(
            puzzle, player_color, prefix_length=self._drill_prefix_for(puzzle)
        )
        self._playback.cancel()
        self._avoided_mistakes = []
        self._seen_mistakes = set()
        self.waiting_for_continue = False
        self._engaged = False
        self._line_demonstrated = False
        self._visit_recorded = False
        self._solve_clock_start = None
        self._carry_mistakes = 0
        self._carry_aids = 0
        self._refresh_arena_rating()
        self.user_store.set_ui(f"last_puzzle:{self.database.database_id}", puzzle.puzzle_id)
        self._skip_first_var.set(puzzle.skip_first_move)
        self._update_favorite_button()
        self._layout.board.set_orientation(player_color)
        self._layout.board.clear_annotations()
        self._layout.board.set_control_overlay(ControlOverlayMode.OFF)
        # An engine that was only auto-started for a threat query is paused
        # between puzzles; user-enabled analysis keeps running.
        if not self._analysis_user_enabled and self.engine_controller.state == EngineState.RUNNING:
            self.engine_controller.pause()
        self._refresh_from_session(self._opening_status())
        self._user_notes.load_current()
        if self.session.in_prefix:
            self._start_prefix_recap()
        elif self._should_demonstrate():
            self._start_line_demonstration()
        elif not self.session.is_complete and self.session.board.turn != self.session.player_color:
            self.cancel_computer_reply()
            self._computer_reply_after_id = self.root.after(
                COMPUTER_REPLY_DELAY_MS, self._play_computer_reply
            )
        else:
            self._maybe_start_solve_clock()

    def previous_puzzle(self) -> None:
        if self.database is None or self.database.count() == 0:
            return
        if self.current_index <= 0:
            return
        if not self._settle_current_arena_puzzle():
            return
        self._user_notes.save_now()
        self.current_index -= 1
        self.load_current_puzzle()

    def next_puzzle(self) -> None:
        if self.database is None or self.database.count() == 0:
            return
        at_end = self.current_index >= self.database.count() - 1
        if at_end and not self.arena_mode:
            return
        if not self._settle_current_arena_puzzle():
            return
        if at_end and self._arena_refill() <= 0:
            self._status_var.set("No new puzzles available.")
            return
        self._user_notes.save_now()
        self.current_index += 1
        self.load_current_puzzle()

    def go_to_puzzle(self) -> None:
        if self.database is None or self.database.count() == 0:
            self._status_var.set("No puzzles loaded")
            return
        number = simpledialog.askinteger(
            "Go to puzzle",
            f"Puzzle number (1-{self.database.count()}):",
            parent=self.root,
            minvalue=1,
            maxvalue=self.database.count(),
        )
        if number is None or number - 1 == self.current_index:
            return
        if not self._settle_current_arena_puzzle():
            return
        self._user_notes.save_now()
        self.current_index = number - 1
        self.load_current_puzzle()

    def on_move_requested(self, move: chess.Move, *, animate: bool = True) -> None:
        if self._playback.active:
            self._status_var.set(f"Watching the line - press {CONTINUE_KEY} to continue.")
            return
        if self.session is None:
            board = self._layout.board.state.board.copy(stack=False)
            if move in board.legal_moves:
                board.push(move)
                self._layout.board.advance_position(board, move, animate=animate)
                self._status_var.set(f"Played {move.uci()}")
            else:
                self._layout.board.flash_move(move)
                self._status_var.set(f"Illegal move: {move.uci()}")
            return

        board_before = self.session.board.copy(stack=False)
        result = self.session.play_user_move(move)
        if result not in (MoveResult.ILLEGAL, MoveResult.WAITING):
            self._engaged = True
        if result in (MoveResult.CORRECT, MoveResult.COMPLETE):
            message = "Puzzle complete." if result == MoveResult.COMPLETE else "Correct."
            self._apply_correct_move(result, move, board_before, message, animate=animate)
            return
        if result == MoveResult.ALTERNATIVE:
            self._layout.board.flash_move(move)
            self._status_var.set(f"Also playable - but this puzzle trains {self._expected_san()}.")
            return
        if result == MoveResult.MISTAKE:
            mistake_line = self.session.last_mistake_line
            if mistake_line is not None:
                # The mistake is played onto the board and punished; the
                # playback rewinds to this position when it finishes. It
                # supplies the move sound itself -- play_error() here would
                # double it (both resolve to move.wav).
                self._seen_mistakes.add((self.session.board.fen(), mistake_line.move.uci()))
                self._playback.start(mistake_line, animate_first=animate)
            else:
                self.audio.play_error()
                self._layout.board.flash_move(move)
                self._status_var.set("Incorrect move.")
            return
        messages = {
            MoveResult.ILLEGAL: "Illegal move.",
            MoveResult.INCORRECT: "Incorrect move.",
            MoveResult.WAITING: "Waiting for your side to move.",
        }
        if result in (MoveResult.ILLEGAL, MoveResult.INCORRECT):
            self.audio.play_error()
        self._layout.board.flash_move(move)
        self._status_var.set(messages.get(result, "Incorrect move."))

    def show_threats(self) -> None:
        """Ask the engine what the opponent would play if we passed."""
        board = self._current_analysis_board()
        if board is None:
            return
        if board.is_game_over():
            self._status_var.set("The game is over in this position.")
            return
        if board.is_check():
            self._status_var.set("You are in check - the check itself is the threat.")
            return
        if self.engine_controller.state != EngineState.RUNNING:
            error = self.engine_controller.start()
            if error:
                messagebox.showerror("Show threat", error, parent=self.root)
                return
            self._update_analysis_button_label()
        threat_board = board.copy(stack=False)
        threat_board.push(chess.Move.null())
        # Re-wrap the FEN so the engine never sees a null move in the stack.
        self.engine_controller.analyse_if_running(chess.Board(threat_board.fen()), purpose="threat")
        self._ensure_engine_polling()
        if self.session is not None:
            self._engaged = True
            self.session.record_aid_used()
        self._status_var.set("Looking for the opponent's threat...")

    def _show_threat_result(self, move: chess.Move | None) -> None:
        if move is None:
            self._status_var.set("No immediate threat found.")
            return
        self._layout.board.set_threat_move(move)
        self._status_var.set(f"Threat: {self._threat_san(move)}")

    def _threat_san(self, move: chess.Move) -> str:
        board = self._current_analysis_board()
        if board is None:
            return move.uci()
        threat_board = board.copy(stack=False)
        threat_board.push(chess.Move.null())
        try:
            return threat_board.san(move)
        except ValueError:
            return move.uci()

    def toggle_hanging_overlay(self) -> None:
        self._toggle_overlay(ControlOverlayMode.HANGING, "Hanging pieces highlighted.")

    def toggle_contested_overlay(self) -> None:
        self._toggle_overlay(
            ControlOverlayMode.CONTROL,
            "Contested squares: blue = White outnumbers, red = Black; denser = bigger edge.",
        )

    def _toggle_overlay(self, mode: ControlOverlayMode, on_message: str) -> None:
        board_view = self._layout.board
        current = board_view.state.control_overlay
        new_mode = ControlOverlayMode.OFF if current is mode else mode
        board_view.set_control_overlay(new_mode)
        if current is ControlOverlayMode.OFF and self.session is not None:
            self._engaged = True
            self.session.record_aid_used()
        self._status_var.set(on_message if new_mode is mode else "Insight overlay hidden.")

    def show_hint(self) -> None:
        # During variation playback the board is not at the session position,
        # so a hint would point at a piece that may not even be there.
        if self._playback.active:
            return
        if self.session is None or self.session.expected_move is None:
            return
        self._engaged = True
        self.session.record_aid_used()
        move = self.session.expected_move
        self._layout.board.show_hint_square(move.from_square)
        piece = self.session.board.piece_at(move.from_square)
        label = chess.piece_name(piece.piece_type) if piece is not None else "piece"
        self._status_var.set(f"Hint: move the {label} on {chess.square_name(move.from_square)}.")

    def play_next_move_for_user(self) -> None:
        if self._playback.advance():
            return
        if self._avoided_mistakes and self.session is not None and self.session.is_complete:
            fen, mistake_line = self._avoided_mistakes.pop(0)
            self._seen_mistakes.add((fen, mistake_line.move.uci()))
            self._playback.start(mistake_line, origin=chess.Board(fen))
            return
        # Nothing left to show on a solved puzzle: the key that cleared the
        # earlier stops finishes the job. Only where something was going to
        # advance anyway -- otherwise the status bar never promised it.
        if self.session is not None and self.session.is_complete and self.option("auto_advance"):
            self.next_puzzle()
            return
        if self.session is None or self.session.expected_move is None:
            return
        if self.waiting_for_continue:
            self.waiting_for_continue = False
            self._play_computer_reply()
            return
        if self.session.board.turn != self.session.player_color:
            self._play_computer_reply()
            return
        # Reaching here means we are playing the user's own move for them on their
        # turn -- that is an aid. The continue-after-comment and computer-reply
        # cases returned above and do not count.
        self._engaged = True
        self.session.record_aid_used()
        move = self.session.expected_move
        board_before = self.session.board.copy(stack=False)
        result = self.session.play_user_move(move)
        status = "Puzzle complete." if result == MoveResult.COMPLETE else "Move played."
        if result in (MoveResult.CORRECT, MoveResult.COMPLETE):
            self._apply_correct_move(result, move, board_before, status)
        else:
            self._refresh_from_session(status, move)

    def _apply_correct_move(
        self,
        result: MoveResult,
        move: chess.Move,
        board_before: chess.Board,
        status: str,
        *,
        animate: bool = True,
    ) -> None:
        assert self.session is not None
        self.audio.play_move(board_before, move, self.session.board)
        self._refresh_from_session(status, move, animate=animate)
        self._layout.board.flash_move(move, FLASH_CORRECT_COLOR)
        if result == MoveResult.CORRECT:
            self._schedule_computer_reply()
        elif result == MoveResult.COMPLETE:
            self._finish_puzzle()

    def _expected_san(self) -> str:
        assert self.session is not None
        move = self.session.expected_move
        if move is None:
            return ""
        try:
            return self.session.board.san(move)
        except ValueError:
            return move.uci()

    def _finish_puzzle(self) -> None:
        """Completion housekeeping, then whatever the user asked to see.

        One rule, the same in every mode: the puzzle advances once nothing is
        waiting on the user. Each thing they asked for -- a marked mistake to
        review, an unread comment -- holds the puzzle open with the message
        that says so, and the continue key clears one of them at a time.
        """
        assert self.session is not None
        self._record_solve()
        self._avoided_mistakes = self._mistakes_to_offer()
        waiting = self._post_solve_stop()
        if waiting is not None:
            self._status_var.set(waiting)
            return
        self._maybe_auto_advance()

    def _mistakes_to_offer(self) -> list[tuple[str, MistakeLine]]:
        """Marked mistakes on this line that the user neither played nor saw."""
        assert self.session is not None
        if not self.option("show_avoided_mistakes"):
            return []
        return [
            (fen, mistake_line)
            for fen, mistake_line in self.session.avoided_mistakes()
            if (fen, mistake_line.move.uci()) not in self._seen_mistakes
        ]

    def _post_solve_stop(self) -> str | None:
        """Message for the first thing waiting on the user, or None."""
        assert self.session is not None
        if self._avoided_mistakes:
            return f"Puzzle complete - press {CONTINUE_KEY} to see the mistake you avoided."
        # A final comment only has to hold the puzzle open when something
        # would otherwise take it away.
        if (
            self.option("auto_advance")
            and self.option("stop_at_comments")
            and self.session.current_comment.strip()
        ):
            return f"Puzzle complete - press {CONTINUE_KEY} for the next puzzle."
        return None

    def _drill_prefix_for(self, puzzle: Puzzle) -> int:
        """Recap length for repertoire decks: where this line joins the previous one."""
        if not self._repertoire_deck:
            return 0
        if not self.option("start_lines_at_divergence") or self.current_index <= 0:
            return 0
        return drill_prefix_length(self.database.puzzle_at(self.current_index - 1), puzzle)

    def _start_prefix_recap(self) -> None:
        """Fast-forward the moves shared with the previous line, animated.

        The recap advances the real session (unlike mistake_line playback's
        scratch board): these are the line's own moves, just not graded.
        Board input during the recap is answered with WAITING by the session."""
        self.cancel_computer_reply()
        self.cancel_prefix_recap()
        self._status_var.set("Recap - watch the line join.")
        self._prefix_after_id = self.root.after(COMPUTER_REPLY_DELAY_MS, self._play_prefix_step)

    def cancel_prefix_recap(self) -> None:
        if self._prefix_after_id is not None:
            self.root.after_cancel(self._prefix_after_id)
            self._prefix_after_id = None

    def _play_prefix_step(self) -> None:
        self._prefix_after_id = None
        if self.session is None or not self.session.in_prefix:
            return
        board_before = self.session.board.copy(stack=False)
        move = self.session.play_prefix_move()
        if move is None:
            return
        self.audio.play_move(board_before, move, self.session.board)
        if self.session.in_prefix:
            self._refresh_from_session("Recap - watch the line join.", move)
            self._prefix_after_id = self.root.after(
                PREFIX_RECAP_STEP_DELAY_MS, self._play_prefix_step
            )
            return
        # Divergence point reached: demonstrate a first-encounter line, or
        # hand over to the normal solving flow.
        if self._should_demonstrate():
            self._refresh_from_session("Recap done - now watch the new moves.", move)
            # One step of breathing room: starting the lesson in the same tick
            # would land its first move (sound and animation) on top of the
            # recap move that just played.
            self._prefix_after_id = self.root.after(
                PREFIX_RECAP_STEP_DELAY_MS, self._start_line_demonstration
            )
        elif not self.session.is_complete and self.session.board.turn != self.session.player_color:
            self._refresh_from_session("Recap done.", move)
            self._schedule_computer_reply()
        else:
            self._refresh_from_session("The line continues here - your move.", move)
            self._maybe_start_solve_clock()

    def _should_demonstrate(self) -> bool:
        """A never-attempted repertoire line is demonstrated before the quiz.

        Recall within moments of first exposure is what commits a line to
        memory; browsing past a line does not count as knowing it (only
        engaged visits record attempts), and one demonstration per visit is
        enough -- a reset goes straight to the retry.
        """
        if self.session is None or self.session.is_complete or self._line_demonstrated:
            return False
        if not self._repertoire_deck:
            return False
        if not self.option("demonstrate_new_lines"):
            return False
        return not self.user_store.has_solved(self.session.puzzle.puzzle_id)

    def _start_line_demonstration(self) -> None:
        """Play the not-yet-drilled part of the line as a lesson.

        The session stays at the quiz point (the lesson runs on a scratch
        board); comments[i + 1] annotates moves[i], matching the mainline
        convention."""
        session = self.session
        assert session is not None
        self._line_demonstrated = True
        start = session.move_index
        moves = list(session.puzzle.moves[start:])
        comments = [
            session.puzzle.comments[index] if index < len(session.puzzle.comments) else ""
            for index in range(start + 1, start + 1 + len(moves))
        ]
        self._playback.start_lesson(moves, comments)

    def _resume_after_lesson(self) -> None:
        """Quiz the line just shown: the lesson rewound to the quiz point."""
        if self.session is None or self.session.is_complete:
            return
        if self.session.board.turn != self.session.player_color:
            self._schedule_computer_reply()
            return
        self._status_var.set("Your turn - play the line from here.")
        self._maybe_start_solve_clock()

    def _schedule_computer_reply(self) -> None:
        self.cancel_computer_reply()
        if (
            self.session is None
            or self.session.is_complete
            or self.session.board.turn == self.session.player_color
        ):
            return
        if self.option("stop_at_comments") and self.session.current_comment.strip():
            self.waiting_for_continue = True
            self._status_var.set(f"Correct - press {CONTINUE_KEY} to continue.")
            return
        self._computer_reply_after_id = self.root.after(
            COMPUTER_REPLY_DELAY_MS, self._play_computer_reply
        )

    def cancel_computer_reply(self) -> None:
        if self._computer_reply_after_id is not None:
            self.root.after_cancel(self._computer_reply_after_id)
            self._computer_reply_after_id = None

    def _play_computer_reply(self) -> None:
        self._computer_reply_after_id = None
        if self.session is None:
            return
        self.waiting_for_continue = False
        board_before = self.session.board.copy(stack=False)
        move = self.session.play_computer_move()
        if move is None:
            return
        self.audio.play_move(board_before, move, self.session.board)
        status = "Puzzle complete." if self.session.is_complete else "Your move."
        self._refresh_from_session(status, move)
        if self.session.is_complete:
            self._finish_puzzle()
        else:
            self._maybe_start_solve_clock()

    def _refresh_from_session(
        self,
        status: str,
        animated_move: chess.Move | None = None,
        *,
        animate: bool = True,
    ) -> None:
        if self.session is None:
            return
        self._layout.board.advance_position(
            self.session.board,
            animated_move,
            clear_annotations=animated_move is not None,
            animate=animate,
        )
        self._request_engine_analysis()
        self._title_var.set(self.session.puzzle.title)
        self._update_puzzle_info()
        self._refresh_comment_view()
        self._status_var.set(status)

    def _player_color_for_puzzle(self, puzzle: Puzzle) -> chess.Color:
        if puzzle.skip_first_move and puzzle.moves:
            return not puzzle.side_to_move
        return puzzle.side_to_move

    def _opening_status(self) -> str:
        if self.session is None:
            return ""
        if self.session.in_prefix:
            return "Recap - watch the line join."
        if self.session.puzzle.skip_first_move and self.session.expected_move is not None:
            return "Computer will play the first move."
        return "Play the first move."

    def _update_puzzle_info(self) -> None:
        if self.session is None:
            self.clear_puzzle_info()
            return
        session = self.session
        puzzle = session.puzzle
        info = self._info_vars
        kind = self.database.kind if self.database is not None else ""
        display = info_display_for(kind, complete=session.is_complete)

        position = str(self.current_index + 1)
        if display.show_deck_total:
            total = self.database.count() if self.database is not None else 0
            position = f"{position} / {total}"
        if display.show_rating and self._arena_rating is not None:
            position = f"{position} — rating {round(self._arena_rating)}"
        info["Puzzle"].set(position)

        if display.show_move_progress:
            info["Move"].set(f"{session.move_index} / {len(puzzle.moves)}")
            self._move_progress.set(
                session.move_index / len(puzzle.moves) if puzzle.moves else 0.0
            )
        else:
            info["Move"].set(HIDDEN_TEXT)
            self._move_progress.set(0.0)

        if session.is_complete:
            info["Turn"].set("✓ Solved")
        else:
            info["Turn"].set("○ White" if session.board.turn == chess.WHITE else "● Black")
        info["Side"].set("White" if session.player_color == chess.WHITE else "Black")
        info["Start"].set("Computer first" if puzzle.skip_first_move else "You first")

        if not display.show_theme:
            info["Theme"].set(HIDDEN_TEXT)
        elif puzzle.theme:
            theme_progress = (
                self.database.theme_position(self.current_index)
                if self.database is not None
                else None
            )
            if theme_progress is not None:
                theme_pos, theme_total = theme_progress
                info["Theme"].set(f"{puzzle.theme} [{theme_pos}/{theme_total}]")
            else:
                info["Theme"].set(puzzle.theme)
        else:
            info["Theme"].set("-")

    def clear_puzzle_info(self) -> None:
        for var in self._info_vars.values():
            var.set("-")
        self._move_progress.set(0.0)

    def _maybe_auto_advance(self) -> None:
        if self.database is None or not self.option("auto_advance"):
            return
        # An arena has no fixed end: next_puzzle refills the deck when the
        # last queued puzzle is done, so advancing keeps the stream going.
        at_end = self.current_index >= self.database.count() - 1
        if self.arena_mode or not at_end:
            self.root.after(AUTO_NEXT_DELAY_MS, self.next_puzzle)

    def _maybe_start_solve_clock(self) -> None:
        if self.session is None or self._solve_clock_start is not None:
            return
        if not self.session.is_complete and self.session.board.turn == self.session.player_color:
            self._solve_clock_start = time.monotonic()

    def _record_solve(self) -> None:
        if self._visit_recorded or self.session is None:
            return
        mistakes = self.session.mistakes + self._carry_mistakes
        aids = self.session.aids_used + self._carry_aids
        database_id, database_path = self._attempt_locator()
        self.user_store.record_attempt(
            Attempt(
                puzzle_id=self.session.puzzle.puzzle_id,
                at=now_iso(),
                outcome="solved",
                mistakes=mistakes,
                aids=aids,
                grade=grade_solve(mistakes, aids),
                duration_ms=self._visit_duration_ms(),
                database_id=database_id,
                database_path=database_path,
                puzzle_rating=puzzle_rating_of(self.session.puzzle),
            )
        )
        self._visit_recorded = True
        self._refresh_session_stats()
        self._announce_arena_rating()

    def _finalize_visit(self) -> None:
        if self.session is None or self._visit_recorded or not self._engaged:
            return
        if self.session.is_complete:
            return
        database_id, database_path = self._attempt_locator()
        self.user_store.record_attempt(
            Attempt(
                puzzle_id=self.session.puzzle.puzzle_id,
                at=now_iso(),
                outcome="gave_up",
                mistakes=self.session.mistakes + self._carry_mistakes,
                aids=self.session.aids_used + self._carry_aids,
                grade="again",
                duration_ms=self._visit_duration_ms(),
                database_id=database_id,
                database_path=database_path,
                puzzle_rating=puzzle_rating_of(self.session.puzzle),
            )
        )
        self._visit_recorded = True
        self._refresh_session_stats()

    # --- arena (rated session) support --------------------------------------

    @property
    def arena_mode(self) -> bool:
        return (
            self.database is not None
            and not self.favorites_view
            and self.database.kind == DECK_KIND_ARENA
        )

    def _refresh_arena_rating(self) -> None:
        if not self.arena_mode:
            self._arena_rating = None
            return
        assert self.database is not None
        config = read_arena_config(self.database)
        self._arena_rating = session_rating(
            self.user_store.connection, self.database.database_id, config.start_rating
        )

    def _announce_arena_rating(self) -> None:
        """After a rated solve: recompute and show the rating with its delta."""
        if not self.arena_mode:
            return
        before = self._arena_rating
        self._refresh_arena_rating()
        if self._arena_rating is None:
            return
        delta = round(self._arena_rating) - round(before) if before is not None else 0
        self._status_var.set(f"Puzzle complete — rating {round(self._arena_rating)} ({delta:+d})")
        self._update_puzzle_info()

    def _settle_current_arena_puzzle(self) -> bool:
        """Settle the current rated puzzle before navigating away from it.

        An engaged unfinished visit is finalized as a loss here -- before any
        refill runs -- so the next batch is sampled at the post-loss rating
        and an empty refill cannot drop the record (finalizing only in
        load_current_puzzle would do both). An untouched, never-attempted
        puzzle takes a deliberate give-up or a cancel -- never a free skip.
        Completed or already-recorded visits, and untouched puzzles that were
        attempted before (browsing history), pass through untouched."""
        if not self.arena_mode or self.session is None:
            return True
        if self._visit_recorded or self.session.is_complete:
            return True
        assert self.database is not None
        if not self._engaged:
            attempted = self.user_store.deck_attempted_ids(self.database.database_id)
            if self.session.puzzle.puzzle_id in attempted:
                return True
            if not messagebox.askyesno(
                "Give up puzzle?",
                "Leaving this puzzle unsolved counts as a rated loss. Give it up?",
                parent=self.root,
            ):
                return False
            self._engaged = True
        self._finalize_visit()
        self._refresh_arena_rating()
        return True

    def _arena_refill(self) -> int:
        """Append the next rating-banded batch to the arena deck."""
        assert self.database is not None
        self.root.configure(cursor="watch")
        self.root.update_idletasks()
        try:
            rating = self._arena_rating
            if rating is None:
                config = read_arena_config(self.database)
                rating = float(config.start_rating)
            return refill(self.database, rating)
        except FileNotFoundError:
            messagebox.showerror(
                "Lichess CSV not found",
                "The CSV file this session samples from is missing. The queued puzzles"
                " still work; restore the CSV to get new ones.",
                parent=self.root,
            )
            return 0
        except Exception as exc:
            messagebox.showerror("Could not fetch puzzles", str(exc), parent=self.root)
            return 0
        finally:
            self.root.configure(cursor="")

    def start_arena_session(self) -> None:
        self._user_notes.save_now()
        self._database.start_arena_session()

    def continue_arena_session(self) -> None:
        self._user_notes.save_now()
        self._database.continue_arena_session()

    def manage_arena_sessions(self) -> None:
        self._user_notes.save_now()
        self._database.manage_arena_sessions()

    def review_arena_mistakes(self) -> None:
        self._user_notes.save_now()
        self._database.review_arena_mistakes()

    def _attempt_locator(self) -> tuple[str, str]:
        """Where the current puzzle's content lives, for the review queue.

        In a favorites/review view the on-screen database is in-memory, so the
        locator comes from the puzzle's source ref instead."""
        if self.favorites_view:
            source = self._current_favorite_source()
            return (source.database_id, source.database_path) if source is not None else ("", "")
        if self.database is not None and self.database_path is not None:
            return self.database.database_id, str(self.database_path)
        return ("", "")

    def _visit_duration_ms(self) -> int | None:
        if self._solve_clock_start is None:
            return None
        return int((time.monotonic() - self._solve_clock_start) * 1000)

    def _refresh_session_stats(self) -> None:
        # No point querying for a hidden HUD; recompute on demand when re-shown.
        if not self.option("show_session_stats"):
            return
        summary = attempt_summary(self.user_store.connection, since=self._stats_anchor)
        self._session_stats_vars["Attempted"].set(str(summary.attempted))
        self._session_stats_vars["Solved"].set(self._solved_summary_text(summary))
        self._session_stats_vars["Total"].set(format_duration_ms(summary.total_ms))
        self._session_stats_vars["Average"].set(format_duration_ms(summary.avg_ms))

    def reset_session_stats(self) -> None:
        self._stats_anchor = now_iso()
        self._refresh_session_stats()

    def show_statistics(self) -> None:
        StatisticsDialog(self.root, self.user_store.connection).show()

    def manage_userdata(self) -> None:
        self._user_notes.save_now()
        self._finalize_visit()
        self._database.manage_userdata()

    def _solved_summary_text(self, summary: AttemptSummary) -> str:
        if summary.solved_percent is None:
            return str(summary.solved)
        return f"{summary.solved} ({summary.solved_percent}%)"

    def toggle_current_favorite(self) -> None:
        if self.session is None:
            return
        if self.favorites_view and not self.review_view:
            self._remove_current_favorite_source()
            return
        if self.review_view:
            source = self._current_favorite_source()
            if source is None:
                self._status_var.set("Favorite source unavailable.")
                return
            database_id, database_path = source.database_id, source.database_path
        elif self.database is not None and self.database_path is not None:
            database_id, database_path = self.database.database_id, str(self.database_path)
        else:
            self._status_var.set("Open the source deck to change favorites.")
            return
        puzzle_id = self.session.puzzle.puzzle_id
        if self.user_store.is_favorite(puzzle_id, database_id):
            self.user_store.remove_favorite(puzzle_id, database_id)
            self._status_var.set("Removed from favorites.")
        else:
            self.user_store.add_favorite(puzzle_id, database_id, database_path)
            self._status_var.set("Added to favorites.")
        self._update_favorite_button()

    def _update_favorite_button(self) -> None:
        icon = "favorite_on.png" if self._current_puzzle_favorited() else "favorite_off.png"
        self._layout.set_toolbar_button_icon(self._layout.favorite_button, icon, "Favorite")

    def _current_puzzle_favorited(self) -> bool:
        if self.session is None or self.database is None:
            return False
        if self.review_view:
            source = self._current_favorite_source()
            return source is not None and self.user_store.is_favorite(
                source.puzzle_id, source.database_id
            )
        if self.favorites_view:
            return self._current_favorite_source() is not None
        return self.user_store.is_favorite(self.session.puzzle.puzzle_id, self.database.database_id)

    def _current_favorite_source(self) -> FavoriteRef | None:
        if (
            not self.favorites_view
            or self.current_index < 0
            or self.current_index >= len(self.favorite_sources)
        ):
            return None
        return self.favorite_sources[self.current_index]

    def _remove_current_favorite_source(self) -> None:
        source = self._current_favorite_source()
        if source is None:
            self._status_var.set("Favorite source unavailable.")
            return
        self.user_store.remove_favorite(source.puzzle_id, source.database_id)
        self.favorite_sources.pop(self.current_index)
        if self.database is not None:
            self.database.delete_puzzles([self.current_index + 1])
            if self.database.count() == 0:
                self.current_index = -1
                self._database.show_empty_state("Removed from favorites.")
                return
            self.current_index = min(self.current_index, self.database.count() - 1)
            self.load_current_puzzle()
        self._status_var.set("Removed from favorites.")

    def view_favorites_this_deck(self) -> None:
        self._database.view_favorites(scope="deck")

    def view_all_favorites(self) -> None:
        self._database.view_favorites(scope="all")

    def review_mistakes_this_deck(self) -> None:
        self._database.review_mistakes(scope="deck")

    def review_all_mistakes(self) -> None:
        self._database.review_mistakes(scope="all")

    def export_favorites_this_deck(self) -> None:
        self._database.export_favorites(scope="deck")

    def export_all_favorites(self) -> None:
        self._database.export_favorites(scope="all")

    def delete_current_puzzle(self) -> None:
        self._database.delete_current_puzzle()

    def export_database_to_pgn(self) -> None:
        if self.database is None:
            self._status_var.set("No database open.")
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export to PGN",
            defaultextension=".pgn",
            filetypes=(("PGN files", "*.pgn"), ("All files", "*.*")),
        )
        if not path:
            return
        count = export_puzzles_to_pgn(self.database.iter_puzzles(), path)
        self._status_var.set(f"Exported {count} puzzle(s).")

    def show_pgn_viewer(self) -> None:
        if self.session is None:
            return
        if self._pgn_viewer is not None and self._pgn_viewer.winfo_exists():
            self._pgn_viewer.lift()
            return
        self._pgn_viewer = PgnViewer(
            self.root,
            self.session.puzzle,
            pgn_for_puzzle(self.session.puzzle),
            presenter=self.presenter,
            player_color=self.session.player_color,
            theme=self.theme_service.current,
        )
