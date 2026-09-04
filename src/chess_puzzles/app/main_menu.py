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
            label="Open Course File...",
            accelerator=MENU_ACCELERATORS[MainShortcuts.OPEN_DATABASE],
            command=window.open_database,
        )
        self._file_menu.add_command(
            label="Course Library...",
            accelerator=MENU_ACCELERATORS[MainShortcuts.COURSE_LIBRARY],
            command=window.open_course_library,
        )
        self._recent_menu = tk.Menu(self._file_menu, tearoff=False)
        self._file_menu.add_cascade(label="Open Recent", menu=self._recent_menu)
        self._file_menu.add_command(
            label="Clear Recent Files",
            command=window.clear_recent_databases,
        )
        self._file_menu.add_separator()
        self._file_menu.add_command(
            label="Exit", accelerator=MENU_ACCELERATORS[MainShortcuts.EXIT], command=window.close
        )
        menu_bar.add_cascade(label="File", menu=self._file_menu)

        # Course menu
        database_menu = tk.Menu(menu_bar, tearoff=False)
        # Two ways to get a course: import a PGN you have, or generate one
        # from the Lichess database. Generators live in their own submenu so
        # a new one does not lengthen this menu. The Add Course picker is not
        # repeated here -- it offers exactly the two entries below it, and is
        # what the welcome screen's button opens.
        database_menu.add_command(
            label="Create tactics course from PGN...",
            accelerator=MENU_ACCELERATORS[MainShortcuts.ADD_COURSE],
            command=window.create_database_from_pgn,
        )
        database_menu.add_command(
            label="Import opening course...",
            command=window.import_opening_course,
        )
        generate_menu = tk.Menu(database_menu, tearoff=False)
        generate_menu.add_command(
            label="Sample puzzles...",
            command=window.import_lichess_csv,
        )
        generate_menu.add_command(
            label="Blunder puzzles...",
            command=window.generate_blunder_puzzles,
        )
        database_menu.add_cascade(label="Generate from Lichess", menu=generate_menu)
        database_menu.add_separator()
        database_menu.add_command(
            label="Edit current...",
            command=window.edit_current_database,
        )
        database_menu.add_command(label="Export to PGN...", command=window.export_database_to_pgn)
        database_menu.add_command(
            label="Delete current puzzle...",
            accelerator=MENU_ACCELERATORS[MainShortcuts.DELETE_CURRENT_PUZZLE],
            command=window.delete_current_puzzle,
        )
        menu_bar.add_cascade(label="Courses", menu=database_menu)

        # Training menu: reviewing, favorites, progress -- everything about
        # the user's own training record, as opposed to deck content
        # (Database menu) and board utilities (Tools menu).
        training_menu = tk.Menu(menu_bar, tearoff=False)
        training_menu.add_command(
            label="Start rated session...",
            command=window.start_arena_session,
        )
        training_menu.add_command(
            label="Continue rated session",
            command=window.continue_arena_session,
        )
        training_menu.add_command(
            label="Rated sessions...",
            command=window.manage_arena_sessions,
        )
        # Historical first-try mistakes of the open session -- distinct from
        # the due-review queue below, which is what currently needs training.
        training_menu.add_command(
            label="Session mistakes (rated)",
            command=window.review_arena_mistakes,
        )
        training_menu.add_separator()
        training_menu.add_command(
            label="Review mistakes (this deck)",
            accelerator=MENU_ACCELERATORS[MainShortcuts.REVIEW_DECK],
            command=window.review_mistakes_this_deck,
        )
        training_menu.add_command(
            label="Review all mistakes",
            accelerator=MENU_ACCELERATORS[MainShortcuts.REVIEW_ALL],
            command=window.review_all_mistakes,
        )
        training_menu.add_separator()
        training_menu.add_command(
            label="Toggle favorite",
            accelerator=MENU_ACCELERATORS[MainShortcuts.SAVE_FAVORITE],
            command=window.toggle_current_favorite,
        )
        training_menu.add_command(
            label="View favorites (this deck)", command=window.view_favorites_this_deck
        )
        training_menu.add_command(label="View all favorites", command=window.view_all_favorites)
        training_menu.add_command(
            label="Export favorites (this deck)...", command=window.export_favorites_this_deck
        )
        training_menu.add_command(
            label="Export all favorites...", command=window.export_all_favorites
        )
        training_menu.add_separator()
        training_menu.add_command(label="Statistics...", command=window.show_statistics)
        training_menu.add_separator()
        training_menu.add_command(label="Manage user data...", command=window.manage_userdata)
        menu_bar.add_cascade(label="Training", menu=training_menu)

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
            label="Highlight pieces under pressure",
            accelerator=MENU_ACCELERATORS[MainShortcuts.TOGGLE_UNDER_PRESSURE_OVERLAY],
            command=window.toggle_under_pressure_overlay,
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
        settings_menu.add_command(
            label="Choose font...",
            command=window.choose_font,
        )
        settings_menu.add_separator()
        settings_menu.add_command(
            label="Options...",
            accelerator=MENU_ACCELERATORS[MainShortcuts.CONFIGURE_OPTIONS],
            command=window.configure_options,
        )
        settings_menu.add_command(
            label="Paths...",
            accelerator=MENU_ACCELERATORS[MainShortcuts.CONFIGURE_PATHS],
            command=window.configure_paths,
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
        for index, database_path in enumerate(window.state.settings.recent_database_paths, start=1):
            resolved = window.user_store.library.relocate_known_path(database_path)
            target = resolved or Path(database_path)
            self._recent_menu.add_command(
                label=f"{index}. {target}",
                accelerator=(
                    MENU_ACCELERATORS[MainShortcuts.OPEN_MOST_RECENT] if index == 1 else ""
                ),
                command=lambda path=target: window.open_database(path),
            )
        if not window.state.settings.recent_database_paths:
            self._recent_menu.add_command(label="No recent courses", state=tk.DISABLED)
        self._recent_menu.add_separator()
        clear_state = tk.NORMAL if window.state.settings.recent_database_paths else tk.DISABLED
        self._file_menu.entryconfigure("Clear Recent Files", state=clear_state)

    def _bind_shortcuts(self) -> None:
        window = self.window
        bindings = {
            MainShortcuts.OPEN_DATABASE: window.open_database,
            MainShortcuts.OPEN_MOST_RECENT: window.open_most_recent_course,
            MainShortcuts.COURSE_LIBRARY: window.open_course_library,
            MainShortcuts.ADD_COURSE: window.create_database_from_pgn,
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
            MainShortcuts.TOGGLE_UNDER_PRESSURE_OVERLAY: window.toggle_under_pressure_overlay,
            MainShortcuts.TOGGLE_CONTESTED_OVERLAY: window.toggle_contested_overlay,
            MainShortcuts.TOGGLE_SKIP: window.toggle_current_skip,
            MainShortcuts.TOGGLE_AUTO_NEXT: lambda: window.toggle_option("auto_advance"),
            MainShortcuts.TOGGLE_REFLOW_COMMENTS: lambda: window.toggle_option("reflow_comments"),
            MainShortcuts.GO_TO_PUZZLE: window.go_to_puzzle,
            MainShortcuts.START_THEME: window.start_theme,
            MainShortcuts.CONFIGURE_OPTIONS: window.configure_options,
            MainShortcuts.CONFIGURE_PATHS: window.configure_paths,
            MainShortcuts.CONFIGURE_ENGINES: window.configure_engines,
            MainShortcuts.TOGGLE_ENGINE_ANALYSIS: window.toggle_engine_analysis,
            MainShortcuts.PLAY_VS_ENGINE: window.open_engine_play_window,
            MainShortcuts.BOARD_VISION: window.open_board_vision_window,
            MainShortcuts.REVIEW_DECK: window.review_mistakes_this_deck,
            MainShortcuts.REVIEW_ALL: window.review_all_mistakes,
            MainShortcuts.TOGGLE_COORDINATES: lambda: window.toggle_option("show_coordinates"),
            MainShortcuts.TOGGLE_EVALUATION_BAR: lambda: window.toggle_option("show_evaluation_bar"),
            MainShortcuts.SHOW_SHORTCUTS: window.show_shortcuts_help,
            MainShortcuts.EXIT: window.close,
        }
        for sequence, action in bindings.items():
            window.root.bind(sequence, guarded_shortcut(action))
