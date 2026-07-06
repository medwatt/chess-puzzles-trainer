from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
import tkinter as tk

from chess_puzzles.shortcuts import MENU_ACCELERATORS, MainShortcuts, guarded_shortcut

if TYPE_CHECKING:
    from chess_puzzles.app.main_window import MainWindow


class MainMenuBuilder:
    def __init__(self, window: MainWindow) -> None:
        self.window = window
        menu_bar = tk.Menu(window.root)

        # File menu
        self._file_menu = tk.Menu(menu_bar, tearoff=False)
        self._file_menu.add_command(
            label="Open database...",
            accelerator=MENU_ACCELERATORS[MainShortcuts.OPEN_DATABASE],
            command=window.open_database,
        )
        self._recent_menu = tk.Menu(self._file_menu, tearoff=False)
        self._file_menu.add_cascade(label="Open Recent", menu=self._recent_menu)
        self._file_menu.add_command(
            label="Clear Recent Files",
            command=window.clear_recent_databases,
        )
        self._file_menu.add_separator()
        self._file_menu.add_command(label="Exit", accelerator=MENU_ACCELERATORS[MainShortcuts.EXIT], command=window.close)
        menu_bar.add_cascade(label="File", menu=self._file_menu)

        # Database menu
        database_menu = tk.Menu(menu_bar, tearoff=False)
        database_menu.add_command(
            label="New from PGN...",
            accelerator=MENU_ACCELERATORS[MainShortcuts.NEW_DATABASE_FROM_PGN],
            command=window.create_database_from_pgn,
        )
        database_menu.add_command(
            label="Import from Lichess CSV...",
            accelerator=MENU_ACCELERATORS[MainShortcuts.IMPORT_LICHESS_CSV],
            command=window.import_lichess_csv,
        )
        database_menu.add_command(
            label="Edit current...",
            accelerator=MENU_ACCELERATORS[MainShortcuts.EDIT_DATABASE],
            command=window.edit_current_database,
        )
        database_menu.add_command(label="Export to PGN...", command=window.export_database_to_pgn)
        database_menu.add_command(
            label="Delete current puzzle...",
            accelerator=MENU_ACCELERATORS[MainShortcuts.DELETE_CURRENT_PUZZLE],
            command=window.delete_current_puzzle,
        )
        menu_bar.add_cascade(label="Database", menu=database_menu)

        # Favorites menu
        favorites_menu = tk.Menu(menu_bar, tearoff=False)
        favorites_menu.add_command(
            label="Toggle favorite",
            accelerator=MENU_ACCELERATORS[MainShortcuts.SAVE_FAVORITE],
            command=window.toggle_current_favorite,
        )
        favorites_menu.add_separator()
        favorites_menu.add_command(label="View favorites (this deck)", command=window.view_favorites_this_deck)
        favorites_menu.add_command(label="View all favorites", command=window.view_all_favorites)
        favorites_menu.add_separator()
        favorites_menu.add_command(label="Review mistakes", command=window.review_mistakes)
        favorites_menu.add_separator()
        favorites_menu.add_command(label="Export favorites (this deck)...", command=window.export_favorites_this_deck)
        favorites_menu.add_command(label="Export all favorites...", command=window.export_all_favorites)
        menu_bar.add_cascade(label="Favorites", menu=favorites_menu)

        # Tools menu
        tools_menu = tk.Menu(menu_bar, tearoff=False)
        tools_menu.add_command(
            label="Copy current position",
            accelerator=MENU_ACCELERATORS[MainShortcuts.COPY_POSITION],
            command=window.copy_current_position,
        )
        tools_menu.add_command(
            label="Copy puzzle PGN",
            accelerator=MENU_ACCELERATORS[MainShortcuts.COPY_PGN],
            command=window.copy_current_pgn,
        )
        tools_menu.add_command(
            label="Export board SVG...",
            accelerator=MENU_ACCELERATORS[MainShortcuts.EXPORT_BOARD_SVG],
            command=window.export_board_svg,
        )
        tools_menu.add_command(
            label="Show PGN",
            accelerator=MENU_ACCELERATORS[MainShortcuts.SHOW_PGN],
            command=window.show_pgn_viewer,
        )
        tools_menu.add_separator()
        tools_menu.add_command(
            label="Show threat",
            accelerator=MENU_ACCELERATORS[MainShortcuts.SHOW_THREATS],
            command=window.show_threats,
        )
        tools_menu.add_command(
            label="Highlight hanging pieces",
            accelerator=MENU_ACCELERATORS[MainShortcuts.TOGGLE_HANGING_OVERLAY],
            command=window.toggle_hanging_overlay,
        )
        tools_menu.add_command(
            label="Show contested squares",
            accelerator=MENU_ACCELERATORS[MainShortcuts.TOGGLE_CONTESTED_OVERLAY],
            command=window.toggle_contested_overlay,
        )
        tools_menu.add_separator()
        tools_menu.add_command(
            label="Go to puzzle...",
            accelerator=MENU_ACCELERATORS[MainShortcuts.GO_TO_PUZZLE],
            command=window.go_to_puzzle,
        )
        tools_menu.add_command(
            label="Start theme...",
            accelerator=MENU_ACCELERATORS[MainShortcuts.START_THEME],
            command=window.start_theme,
        )
        tools_menu.add_separator()
        tools_menu.add_command(
            label="Clear marks",
            accelerator=MENU_ACCELERATORS[MainShortcuts.CLEAR_MARKS],
            command=window.clear_marks,
        )
        tools_menu.add_separator()
        tools_menu.add_command(
            label="Board Vision...",
            accelerator=MENU_ACCELERATORS[MainShortcuts.BOARD_VISION],
            command=window.open_board_vision_window,
        )
        tools_menu.add_command(label="Statistics...", command=window.show_statistics)
        menu_bar.add_cascade(label="Tools", menu=tools_menu)

        # Engines menu
        engines_menu = tk.Menu(menu_bar, tearoff=False)
        engines_menu.add_command(
            label="Configure engines...",
            accelerator=MENU_ACCELERATORS[MainShortcuts.CONFIGURE_ENGINES],
            command=window.configure_engines,
        )
        engines_menu.add_separator()
        engines_menu.add_command(
            label="Start analysis",
            accelerator=MENU_ACCELERATORS[MainShortcuts.TOGGLE_ENGINE_ANALYSIS],
            command=window.toggle_engine_analysis,
        )
        engines_menu.add_command(
            label="Play vs Engine",
            accelerator=MENU_ACCELERATORS[MainShortcuts.PLAY_VS_ENGINE],
            command=window.open_engine_play_window,
        )
        menu_bar.add_cascade(label="Engines", menu=engines_menu)

        # Settings menu
        settings_menu = tk.Menu(menu_bar, tearoff=False)
        app_theme_menu = tk.Menu(settings_menu, tearoff=False)
        for theme_id, theme in window.theme_service.themes.items():
            app_theme_menu.add_radiobutton(
                label=theme.name,
                value=theme_id,
                variable=window._ui_theme_var,
                command=lambda value=theme_id: window.set_ui_theme(value),
            )
        settings_menu.add_cascade(label="Application Theme", menu=app_theme_menu)

        board_theme_menu = tk.Menu(settings_menu, tearoff=False)
        for theme_id, theme in window.board_themes.items():
            board_theme_menu.add_radiobutton(
                label=theme.name,
                value=theme_id,
                variable=window._board_theme_var,
                command=lambda value=theme_id: window.set_board_theme(value),
            )
        settings_menu.add_cascade(label="Board Theme", menu=board_theme_menu)

        self._piece_theme_menu = tk.Menu(settings_menu, tearoff=False)
        self.refresh_piece_theme_menu()
        settings_menu.add_cascade(label="Piece Set", menu=self._piece_theme_menu)
        settings_menu.add_checkbutton(
            label="Show coordinates",
            accelerator=MENU_ACCELERATORS[MainShortcuts.TOGGLE_COORDINATES],
            variable=window._coordinates_var,
            command=window.on_coordinates_changed,
        )
        settings_menu.add_checkbutton(
            label="Show PGN after solving",
            variable=window._show_pgn_after_solve_var,
            command=window.on_show_pgn_after_solve_changed,
        )
        settings_menu.add_checkbutton(
            label="Show evaluation bar",
            accelerator=MENU_ACCELERATORS[MainShortcuts.TOGGLE_EVALUATION_BAR],
            variable=window._show_evaluation_bar_var,
            command=window.on_show_evaluation_bar_changed,
        )
        settings_menu.add_checkbutton(
            label="Show session stats",
            variable=window._show_session_stats_var,
            command=window.on_show_session_stats_changed,
        )
        settings_menu.add_checkbutton(
            label="Show user notes",
            variable=window._show_user_notes_var,
            command=window.toggle_user_notes,
        )
        settings_menu.add_checkbutton(
            label="Play sound",
            variable=window._play_sound_var,
            command=window.toggle_play_sound,
        )
        settings_menu.add_command(
            label="Folders...",
            accelerator=MENU_ACCELERATORS[MainShortcuts.CONFIGURE_FOLDERS],
            command=window.configure_folders,
        )
        settings_menu.add_command(
            label="Choose font...",
            accelerator=MENU_ACCELERATORS[MainShortcuts.CHOOSE_FONT],
            command=window.choose_font,
        )
        menu_bar.add_cascade(label="Settings", menu=settings_menu)

        # Help menu
        help_menu = tk.Menu(menu_bar, tearoff=False)
        help_menu.add_command(
            label="Keyboard Shortcuts",
            accelerator=MENU_ACCELERATORS[MainShortcuts.SHOW_SHORTCUTS],
            command=window.show_shortcuts_help,
        )
        help_menu.add_command(label="About Chess-Puzzles-Trainer", command=window.show_about)
        menu_bar.add_cascade(label="Help", menu=help_menu)

        # Attach to the window and wire up dynamic state
        window.root.config(menu=menu_bar)
        self.refresh_recent_menu()
        self._bind_shortcuts()

    def refresh_piece_theme_menu(self) -> None:
        window = self.window
        self._piece_theme_menu.delete(0, tk.END)
        for theme_id, theme in window.piece_themes.items():
            self._piece_theme_menu.add_radiobutton(
                label=theme.name,
                value=theme_id,
                variable=window._piece_theme_var,
                command=lambda value=theme_id: window.set_piece_theme(value),
            )

    def refresh_recent_menu(self) -> None:
        window = self.window
        self._recent_menu.delete(0, tk.END)
        for database_path in window.state.settings.recent_database_paths:
            self._recent_menu.add_command(
                label=database_path,
                command=lambda path=database_path: window.open_database(Path(path)),
            )
        if not window.state.settings.recent_database_paths:
            self._recent_menu.add_command(label="No recent databases", state=tk.DISABLED)
        self._recent_menu.add_separator()
        clear_state = tk.NORMAL if window.state.settings.recent_database_paths else tk.DISABLED
        self._file_menu.entryconfigure("Clear Recent Files", state=clear_state)

    def _bind_shortcuts(self) -> None:
        window = self.window
        bindings = {
            MainShortcuts.OPEN_DATABASE: window.open_database,
            MainShortcuts.NEW_DATABASE_FROM_PGN: window.create_database_from_pgn,
            MainShortcuts.IMPORT_LICHESS_CSV: window.import_lichess_csv,
            MainShortcuts.EDIT_DATABASE: window.edit_current_database,
            MainShortcuts.SAVE_FAVORITE: window.toggle_current_favorite,
            MainShortcuts.DELETE_CURRENT_PUZZLE: window.delete_current_puzzle,
            MainShortcuts.CLEAR_MARKS: window.clear_marks,
            MainShortcuts.COPY_POSITION: window.copy_current_position,
            MainShortcuts.COPY_PGN: window.copy_current_pgn,
            MainShortcuts.EXPORT_BOARD_SVG: window.export_board_svg,
            MainShortcuts.SHOW_PGN: window.show_pgn_viewer,
            MainShortcuts.RESET_PUZZLE: window.reset_position,
            MainShortcuts.FLIP_BOARD: window.flip_board,
            MainShortcuts.NEXT_PUZZLE: window.next_puzzle,
            MainShortcuts.PREVIOUS_PUZZLE: window.previous_puzzle,
            MainShortcuts.SHOW_HINT: window.show_hint,
            MainShortcuts.PLAY_MOVE: window.play_next_move_for_user,
            MainShortcuts.SHOW_THREATS: window.show_threats,
            MainShortcuts.TOGGLE_HANGING_OVERLAY: window.toggle_hanging_overlay,
            MainShortcuts.TOGGLE_CONTESTED_OVERLAY: window.toggle_contested_overlay,
            MainShortcuts.TOGGLE_SKIP: window.toggle_current_skip,
            MainShortcuts.TOGGLE_AUTO_NEXT: window.toggle_auto_next,
            MainShortcuts.TOGGLE_CLEAN_COMMENTS: window.toggle_clean_comments,
            MainShortcuts.GO_TO_PUZZLE: window.go_to_puzzle,
            MainShortcuts.START_THEME: window.start_theme,
            MainShortcuts.CONFIGURE_FOLDERS: window.configure_folders,
            MainShortcuts.CHOOSE_FONT: window.choose_font,
            MainShortcuts.CONFIGURE_ENGINES: window.configure_engines,
            MainShortcuts.TOGGLE_ENGINE_ANALYSIS: window.toggle_engine_analysis,
            MainShortcuts.PLAY_VS_ENGINE: window.open_engine_play_window,
            MainShortcuts.BOARD_VISION: window.open_board_vision_window,
            MainShortcuts.TOGGLE_COORDINATES: window.toggle_coordinates,
            MainShortcuts.TOGGLE_EVALUATION_BAR: window.toggle_show_evaluation_bar,
            MainShortcuts.SHOW_SHORTCUTS: window.show_shortcuts_help,
            MainShortcuts.EXIT: window.close,
        }
        for sequence, action in bindings.items():
            window.root.bind(sequence, guarded_shortcut(action))
