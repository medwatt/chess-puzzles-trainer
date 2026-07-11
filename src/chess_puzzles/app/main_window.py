# imports <<<
from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, font, messagebox, simpledialog

import chess

from chess_puzzles.app.app_state import AppState
from chess_puzzles.app.main_database_actions import MainDatabaseActions
from chess_puzzles.app.main_layout import MainLayoutBuilder
from chess_puzzles.app.main_menu import MainMenuBuilder
from chess_puzzles.app.main_user_notes import MainUserNotes
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
)
from chess_puzzles.board.input import BoardEvent, MoveRequested
from chess_puzzles.dialogs.choice import ChoiceDialog
from chess_puzzles.dialogs.folders import FolderField, FoldersDialog
from chess_puzzles.dialogs.font import FontChooserDialog
from chess_puzzles.dialogs.shortcuts_help import ShortcutsHelpDialog
from chess_puzzles.dialogs.statistics import StatisticsDialog
from chess_puzzles.engine import EngineController, EngineState
from chess_puzzles.engine.config import EngineConfig, load_engine_config, save_engine_config
from chess_puzzles.engine.dialogs import EngineConfigDialog
from chess_puzzles.engine.play_window import EnginePlayWindow
from chess_puzzles.lichess.settings import load_lichess_settings
from chess_puzzles.vision.window import BoardVisionWindow
from chess_puzzles.platform.audio import AudioPlayer
from chess_puzzles.pgn import PgnLoader
from chess_puzzles.pgn.comments import strip_annotation_commands
from chess_puzzles.pgn.exporter import export_puzzles_to_pgn
from chess_puzzles.pgn.utils import pgn_for_puzzle
from chess_puzzles.pgn.viewer import PgnViewer
from chess_puzzles.puzzle import MoveResult, Puzzle, PuzzleSession
from chess_puzzles.puzzle.grade import grade_solve
from chess_puzzles.reports import AttemptSummary, attempt_summary, format_duration_ms
from chess_puzzles.settings.repository import SettingsRepository
from chess_puzzles.store import Attempt, ContentDatabase, FavoriteRef, UserStore, now_iso
from chess_puzzles.settings.theme_repository import UiTheme, available_piece_themes, built_in_board_themes
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

        # View toggles persisted in user settings
        self._coordinates_var = tk.BooleanVar(value=state.settings.show_coordinates)
        self._show_pgn_after_solve_var = tk.BooleanVar(value=state.settings.show_pgn_after_solve)
        self._show_evaluation_bar_var = tk.BooleanVar(value=state.settings.show_evaluation_bar)
        self._show_session_stats_var = tk.BooleanVar(value=state.settings.show_session_stats)
        self._show_user_notes_var = tk.BooleanVar(value=state.settings.show_user_notes)
        self._play_sound_var = tk.BooleanVar(value=state.settings.sound_enabled)

        # Training preferences (persisted in user settings)
        self._skip_first_var = tk.BooleanVar(value=False)
        self._auto_next_var = tk.BooleanVar(value=state.settings.auto_next_enabled)
        self._clean_comments_var = tk.BooleanVar(value=state.settings.clean_comments)
        self._pause_for_comment_var = tk.BooleanVar(value=state.settings.pause_for_comment)

        # Sidebar/status text bound to labels
        self._status_var = tk.StringVar(value="Ready")
        self._title_var = tk.StringVar(value="No puzzle loaded")
        self._info_vars: dict[str, tk.StringVar] = {
            key: tk.StringVar(value="-") for key in ("Puzzle", "Move", "Turn", "Side", "Start", "Theme")
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
        self._visit_recorded = False
        self._solve_clock_start: float | None = None

        # Engine config and analysis controller
        self.engine_config: EngineConfig = load_engine_config()
        self.engine_controller = EngineController(self.engine_config)

        # Computer-reply scheduling (within the current session)
        self._computer_reply_after_id: str | None = None
        self.waiting_for_continue = False

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

    # Menu checkbuttons flip their variable before invoking the command, so
    # the on_*_changed handlers only apply the current value. The keyboard
    # shortcuts bypass the menu, so the toggle_* variants flip the variable
    # themselves first.
    def toggle_coordinates(self) -> None:
        self._coordinates_var.set(not self._coordinates_var.get())
        self.on_coordinates_changed()

    def on_coordinates_changed(self) -> None:
        enabled = bool(self._coordinates_var.get())
        self.presenter.update(show_coordinates=enabled)
        self.save_settings(show_coordinates=enabled)
        self._status_var.set("Coordinates shown" if enabled else "Coordinates hidden")

    def flip_board(self) -> None:
        self._layout.board.set_flipped(not self._layout.board.state.flipped)

    def clear_marks(self) -> None:
        self._layout.board.clear_annotations()

    def reset_position(self) -> None:
        if self.session is None:
            self._layout.board.set_position(chess.Board())
            self._layout.board.set_last_move(None)
            self._status_var.set("Position reset")
            return
        self.cancel_computer_reply()
        self.session.reset()
        self._refresh_from_session("Puzzle reset.")
        self._schedule_computer_reply()

    def close(self) -> None:
        try:
            self._user_notes.save_now()
            self._finalize_visit()
            self.user_store.close()
            self.engine_controller.shutdown()
            self.settings_repository.save(self.state.settings)
        finally:
            self.root.destroy()

    def clear_recent_databases(self) -> None:
        self.save_settings(recent_database_paths=())
        self._menu.refresh_recent_menu()
        self._status_var.set("Recent files cleared")

    def copy_current_position(self) -> None:
        fen = self.session.board.fen() if self.session is not None else self._layout.board.state.board.fen()
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

    def toggle_show_pgn_after_solve(self) -> None:
        self._show_pgn_after_solve_var.set(not self._show_pgn_after_solve_var.get())
        self.on_show_pgn_after_solve_changed()

    def on_show_pgn_after_solve_changed(self) -> None:
        self.save_settings(show_pgn_after_solve=bool(self._show_pgn_after_solve_var.get()))

    def toggle_show_evaluation_bar(self) -> None:
        self._show_evaluation_bar_var.set(not self._show_evaluation_bar_var.get())
        self.on_show_evaluation_bar_changed()

    def on_show_evaluation_bar_changed(self) -> None:
        visible = bool(self._show_evaluation_bar_var.get())
        self._layout.board_frame.set_evaluation_bar_visible(visible)
        self.save_settings(show_evaluation_bar=visible)

    def toggle_user_notes(self) -> None:
        self._user_notes.toggle()

    def apply_user_notes_visibility(self) -> None:
        self._user_notes.apply_visibility()

    def toggle_play_sound(self) -> None:
        enabled = bool(self._play_sound_var.get())
        self.audio.set_enabled(enabled)
        self.save_settings(sound_enabled=enabled)

    def toggle_current_skip(self) -> None:
        if self.session is None or self.database is None:
            return
        value = not self.session.puzzle.skip_first_move
        self.database.set_skip_first_move(self.current_index + 1, value)
        self.load_current_puzzle()

    def toggle_auto_next(self) -> None:
        self._auto_next_var.set(not self._auto_next_var.get())
        self.save_training_preferences()

    def toggle_clean_comments(self) -> None:
        self._clean_comments_var.set(not self._clean_comments_var.get())
        self.on_clean_comments_changed()

    def save_training_preferences(self) -> None:
        self.save_settings(
            auto_next_enabled=bool(self._auto_next_var.get()),
            clean_comments=bool(self._clean_comments_var.get()),
            pause_for_comment=bool(self._pause_for_comment_var.get()),
        )

    def on_clean_comments_changed(self) -> None:
        self.save_training_preferences()
        if self.session is not None:
            self._replace_text(self._layout.comment_view, self._display_comment(self.session.current_comment))

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
        board_theme = self.board_themes.get(settings.board_theme_id, self.board_themes[DEFAULT_BOARD_THEME_ID])
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
            tk_font.configure(family=settings.font_family, size=settings.font_size, weight=weight, slant=slant)

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
        return display_comment(strip_annotation_commands(comment), self._clean_comments_var.get())

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
        theme = ChoiceDialog(self.root, "Start theme", "Theme:", themes, self.active_theme or themes[0]).show_modal()
        if theme is None:
            return
        self.active_theme = theme
        for index, puzzle in enumerate(self.database.iter_puzzles()):
            if puzzle.theme == theme:
                self.current_index = index
                self.load_current_puzzle()
                self._status_var.set(f"Started theme: {theme}")
                return

    def configure_folders(self) -> None:
        settings = self.state.settings
        fields = (
            FolderField(
                key="default_database_directory",
                label="Database folder",
                description="Where database dialogs start and where the Favorites database is kept.",
                value=settings.default_database_directory or "",
            ),
            FolderField(
                key="piece_assets_directory",
                label="Custom pieces folder",
                description=(
                    "Extra piece sets, one sub-folder per set with sprite sheets named "
                    "<set>_<size>.png. A set named like a bundled one replaces it."
                ),
                value=settings.piece_assets_directory or "",
            ),
        )
        result = FoldersDialog(self.root, fields).show_modal()
        if result is None:
            return
        self.save_settings(
            default_database_directory=result["default_database_directory"] or None,
            piece_assets_directory=result["piece_assets_directory"] or None,
        )
        self._reload_piece_themes()
        self._status_var.set("Folders updated.")

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
            messagebox.showerror("Play vs Engine", "Configure a default engine first.", parent=self.root)
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
        csv_path = load_lichess_settings().csv_path
        if not csv_path or not Path(csv_path).is_file():
            messagebox.showerror(
                "Board Vision",
                "Set the Lichess puzzle CSV path first (Database > Import from Lichess CSV...).",
                parent=self.root,
            )
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
            self._engine_poll_after_id = self.root.after(ENGINE_POLL_INTERVAL_MS, self._poll_engine_results)

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
        running = self.engine_controller.state == EngineState.RUNNING and self._analysis_user_enabled
        icon_name = "analysis_pause.png" if running else "analysis_start.png"
        text = "Pause Analysis" if running else "Start Analysis"
        self._layout.set_toolbar_button_icon(self._layout.toggle_analysis_button, icon_name, text)

    def create_database_from_pgn(self) -> None:
        self._user_notes.save_now()
        self._database.create_database_from_pgn()

    def open_database(self, database_path: Path | None = None) -> None:
        self._user_notes.save_now()
        self._database.open_database(database_path)

    def import_lichess_csv(self) -> None:
        self._user_notes.save_now()
        self._database.import_lichess_csv()

    def load_current_puzzle(self) -> None:
        self._finalize_visit()
        if self.database is None or self.current_index < 0 or self.current_index >= self.database.count():
            return
        puzzle = self.database.puzzle_at(self.current_index)
        player_color = self._player_color_for_puzzle(puzzle)
        self.session = PuzzleSession(puzzle, player_color)
        self.waiting_for_continue = False
        self._engaged = False
        self._visit_recorded = False
        self._solve_clock_start = None
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
        if not self.session.is_complete and self.session.board.turn != self.session.player_color:
            self.cancel_computer_reply()
            self._computer_reply_after_id = self.root.after(COMPUTER_REPLY_DELAY_MS, self._play_computer_reply)
        else:
            self._maybe_start_solve_clock()

    def previous_puzzle(self) -> None:
        if self.database is None or self.database.count() == 0:
            return
        if self.current_index <= 0:
            return
        self._user_notes.save_now()
        self.current_index -= 1
        self.load_current_puzzle()

    def next_puzzle(self) -> None:
        if self.database is None or self.database.count() == 0:
            return
        if self.current_index >= self.database.count() - 1:
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
        if number is None:
            return
        self._user_notes.save_now()
        self.current_index = number - 1
        self.load_current_puzzle()

    def on_move_requested(self, move: chess.Move, *, animate: bool = True) -> None:
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
        if result == MoveResult.BLUNDER:
            self.audio.play_error()
            self._layout.board.flash_move(move)
            self._show_refutation()
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
            self.session.record_aid_used()
        self._status_var.set(on_message if new_mode is mode else "Insight overlay hidden.")

    def show_hint(self) -> None:
        if self.session is None or self.session.expected_move is None:
            return
        self.session.record_aid_used()
        move = self.session.expected_move
        self._layout.board.show_hint_square(move.from_square)
        piece = self.session.board.piece_at(move.from_square)
        label = chess.piece_name(piece.piece_type) if piece is not None else "piece"
        self._status_var.set(f"Hint: move the {label} on {chess.square_name(move.from_square)}.")

    def play_next_move_for_user(self) -> None:
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
            self._record_solve()
            self._maybe_show_pgn_after_solve()
            self._maybe_auto_next()

    def _expected_san(self) -> str:
        assert self.session is not None
        move = self.session.expected_move
        if move is None:
            return ""
        try:
            return self.session.board.san(move)
        except ValueError:
            return move.uci()

    def _show_refutation(self) -> None:
        """Show why a NAG-marked mistake fails: the punishing line in the
        status bar, the author's explanation in the comment panel."""
        assert self.session is not None
        refutation = self.session.last_refutation
        if refutation is None:
            self._status_var.set("Incorrect move.")
            return
        board = self.session.board.copy(stack=False)
        sans = [board.san_and_push(refutation.move)]
        for reply in refutation.line:
            sans.append(board.san_and_push(reply))
        if len(sans) > 1:
            self._status_var.set(f"Blunder: {sans[0]} loses to {' '.join(sans[1:])}.")
        else:
            self._status_var.set(f"Blunder: {sans[0]} is a marked mistake.")
        explanation = "\n\n".join(comment for comment in refutation.comments if comment.strip())
        if explanation and hasattr(self._layout, "comment_view"):
            text = f"{' '.join(sans)}\n\n{explanation}"
            self._replace_text(self._layout.comment_view, self._display_comment(text))

    def _schedule_computer_reply(self) -> None:
        self.cancel_computer_reply()
        if self.session is None or self.session.is_complete or self.session.board.turn == self.session.player_color:
            return
        if self._pause_for_comment_var.get() and self.session.current_comment.strip():
            self.waiting_for_continue = True
            self._status_var.set("Correct: press m to continue.")
            return
        self._computer_reply_after_id = self.root.after(COMPUTER_REPLY_DELAY_MS, self._play_computer_reply)

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
            self._record_solve()
            self._maybe_show_pgn_after_solve()
            self._maybe_auto_next()
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
        if hasattr(self._layout, "comment_view"):
            self._replace_text(self._layout.comment_view, self._display_comment(self.session.current_comment))
        self._status_var.set(status)

    def _player_color_for_puzzle(self, puzzle: Puzzle) -> chess.Color:
        if puzzle.skip_first_move and puzzle.moves:
            return not puzzle.side_to_move
        return puzzle.side_to_move

    def _opening_status(self) -> str:
        if self.session is None:
            return ""
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
        total = self.database.count() if self.database is not None else 0
        info["Puzzle"].set(f"{self.current_index + 1} / {total}")
        info["Move"].set(f"{session.move_index} / {len(puzzle.moves)}")
        self._move_progress.set(session.move_index / len(puzzle.moves) if puzzle.moves else 0.0)
        if session.is_complete:
            info["Turn"].set("✓ Solved")
        else:
            info["Turn"].set("○ White" if session.board.turn == chess.WHITE else "● Black")
        info["Side"].set("White" if session.player_color == chess.WHITE else "Black")
        info["Start"].set("Computer first" if puzzle.skip_first_move else "You first")
        if puzzle.theme:
            theme_progress = self.database.theme_position(self.current_index) if self.database is not None else None
            if theme_progress is not None:
                position, theme_total = theme_progress
                info["Theme"].set(f"{puzzle.theme} [{position}/{theme_total}]")
            else:
                info["Theme"].set(puzzle.theme)
        else:
            info["Theme"].set("-")

    def clear_puzzle_info(self) -> None:
        for var in self._info_vars.values():
            var.set("-")
        self._move_progress.set(0.0)

    def _maybe_show_pgn_after_solve(self) -> None:
        if not self._auto_next_var.get() and self._show_pgn_after_solve_var.get():
            self.show_pgn_viewer()

    def _maybe_auto_next(self) -> None:
        if self.database is None:
            return
        if self._auto_next_var.get() and self.current_index < self.database.count() - 1:
            self.root.after(AUTO_NEXT_DELAY_MS, self.next_puzzle)

    def _maybe_start_solve_clock(self) -> None:
        if self.session is None or self._solve_clock_start is not None:
            return
        if not self.session.is_complete and self.session.board.turn == self.session.player_color:
            self._solve_clock_start = time.monotonic()

    def _record_solve(self) -> None:
        if self._visit_recorded or self.session is None:
            return
        database_id, database_path = self._attempt_locator()
        self.user_store.record_attempt(
            Attempt(
                puzzle_id=self.session.puzzle.puzzle_id,
                at=now_iso(),
                outcome="solved",
                mistakes=self.session.mistakes,
                aids=self.session.aids_used,
                grade=grade_solve(self.session.mistakes, self.session.aids_used),
                duration_ms=self._visit_duration_ms(),
                database_id=database_id,
                database_path=database_path,
            )
        )
        self._visit_recorded = True
        self._refresh_session_stats()

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
                mistakes=self.session.mistakes,
                aids=self.session.aids_used,
                grade="again",
                duration_ms=self._visit_duration_ms(),
                database_id=database_id,
                database_path=database_path,
            )
        )
        self._visit_recorded = True
        self._refresh_session_stats()

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
        if not self._show_session_stats_var.get():
            return
        summary = attempt_summary(self.user_store.connection, since=self._stats_anchor)
        self._session_stats_vars["Attempted"].set(str(summary.attempted))
        self._session_stats_vars["Solved"].set(self._solved_summary_text(summary))
        self._session_stats_vars["Total"].set(format_duration_ms(summary.total_ms))
        self._session_stats_vars["Average"].set(format_duration_ms(summary.avg_ms))

    def reset_session_stats(self) -> None:
        self._stats_anchor = now_iso()
        self._refresh_session_stats()

    def on_show_session_stats_changed(self) -> None:
        visible = bool(self._show_session_stats_var.get())
        self._layout.set_session_stats_visible(visible)
        if visible:
            self._refresh_session_stats()
        self.save_settings(show_session_stats=visible)

    def show_statistics(self) -> None:
        StatisticsDialog(self.root, self.user_store.connection).show()

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
            return source is not None and self.user_store.is_favorite(source.puzzle_id, source.database_id)
        if self.favorites_view:
            return self._current_favorite_source() is not None
        return self.user_store.is_favorite(self.session.puzzle.puzzle_id, self.database.database_id)

    def _current_favorite_source(self) -> FavoriteRef | None:
        if not self.favorites_view or self.current_index < 0 or self.current_index >= len(self.favorite_sources):
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

    def review_mistakes(self) -> None:
        self._database.review_mistakes()

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
