from __future__ import annotations

from typing import TYPE_CHECKING, Callable
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from chess_puzzles.board import BoardShortcuts, BoardView
from chess_puzzles.engine.board_analysis_frame import BoardAnalysisFrame
from chess_puzzles.engine.evaluation_bar import EvaluationBar
from chess_puzzles.platform.paths import assets_dir
from chess_puzzles.shortcuts import MENU_ACCELERATORS, MainShortcuts
from chess_puzzles.ui.icon_recolor import RecoloredIconCache
from chess_puzzles.ui.tooltip import ThemedTooltip

if TYPE_CHECKING:
    from chess_puzzles.app.main_window import MainWindow


class MainLayoutBuilder:
    def __init__(self, window: MainWindow) -> None:
        # Builder state
        self.window = window
        self._button_icons = RecoloredIconCache()
        self._button_icon_names: dict[ttk.Button, str] = {}
        self._tooltips: list[ThemedTooltip] = []

        # Root grid: board on the left, sidebar on the right
        window.root.columnconfigure(0, weight=1)
        window.root.rowconfigure(0, weight=1)

        shell = ttk.Frame(window.root, padding=(8, 8, 8, 0))
        shell.grid(row=0, column=0, sticky="nsew")
        shell.columnconfigure(0, weight=3, minsize=420)
        shell.columnconfigure(1, weight=1, minsize=300)
        shell.rowconfigure(0, weight=1)

        # Board and evaluation bar
        board_outer = ttk.Frame(shell)
        board_outer.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        board_outer.columnconfigure(0, weight=1)
        board_outer.rowconfigure(0, weight=1)

        self.board_frame = BoardAnalysisFrame(
            board_outer,
            event_handler=window._handle_board_event,
            evaluation_bar_visible=window.state.settings.show_evaluation_bar,
        )
        self.board_frame.grid(row=0, column=0, sticky="nsew")
        self.board: BoardView = self.board_frame.board
        self.evaluation_bar: EvaluationBar = self.board_frame.evaluation_bar
        window.presenter.register(self.board)
        self.board.focus_set()

        # Bold variant of the default font for emphasized values
        self._bold_font = tkfont.Font(font="TkDefaultFont")
        self._bold_font.configure(weight="bold")

        # Toolbar, sidebar, status bar, first-run welcome panel
        self._build_navigation(shell)
        self._build_sidebar(shell)
        self._build_status_bar()
        self._build_welcome_panel(shell)

        # Board-level keyboard shortcuts (arrow keys, etc.)
        BoardShortcuts(window.root, self.board).bind()

    def _build_navigation(self, shell: ttk.Frame) -> None:
        window = self.window
        navigation = ttk.LabelFrame(shell, text="Puzzle Controls")
        self.navigation = navigation
        navigation.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        navigation_buttons = ttk.Frame(navigation)
        navigation_buttons.pack(anchor=tk.CENTER, pady=2)
        self._toolbar_button(
            navigation_buttons,
            "Previous",
            window.previous_puzzle,
            "previous.png",
            MainShortcuts.PREVIOUS_PUZZLE,
        )
        self._toolbar_button(
            navigation_buttons,
            "Next",
            window.next_puzzle,
            "next.png",
            MainShortcuts.NEXT_PUZZLE,
        )
        self._toolbar_button(
            navigation_buttons,
            "Reset",
            window.reset_position,
            "reset.png",
            MainShortcuts.RESET_PUZZLE,
        )
        self._toolbar_button(
            navigation_buttons,
            "Flip",
            window.flip_board,
            "flip.png",
            MainShortcuts.FLIP_BOARD,
        )
        ttk.Separator(navigation_buttons, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=(4, 8))
        self._toolbar_button(
            navigation_buttons,
            "Hint",
            window.show_hint,
            "hint.png",
            MainShortcuts.SHOW_HINT,
        )
        self._toolbar_button(
            navigation_buttons,
            "Play Move",
            window.play_next_move_for_user,
            "advance_move.png",
            MainShortcuts.PLAY_MOVE,
        )
        self._toolbar_button(
            navigation_buttons,
            "Show PGN",
            window.show_pgn_viewer,
            "show_pgn.png",
            MainShortcuts.SHOW_PGN,
        )
        ttk.Separator(navigation_buttons, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=(4, 8))
        self.favorite_button = self._toolbar_button(
            navigation_buttons,
            "Favorite",
            window.toggle_current_favorite,
            "favorite_off.png",
            MainShortcuts.SAVE_FAVORITE,
        )
        self._toolbar_button(
            navigation_buttons,
            "Delete Puzzle",
            window.delete_current_puzzle,
            "delete_puzzle.png",
            MainShortcuts.DELETE_CURRENT_PUZZLE,
        )
        ttk.Separator(navigation_buttons, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=(4, 8))
        self.toggle_analysis_button = self._toolbar_button(
            navigation_buttons,
            "Start Analysis",
            window.toggle_engine_analysis,
            "analysis_start.png",
            MainShortcuts.TOGGLE_ENGINE_ANALYSIS,
        )
        self._toolbar_button(
            navigation_buttons,
            "Play vs Engine",
            window.open_engine_play_window,
            "play_vs_engine.png",
            MainShortcuts.PLAY_VS_ENGINE,
        )

    def _build_sidebar(self, shell: ttk.Frame) -> None:
        window = self.window
        sidebar = ttk.Frame(shell, padding=(0, 2, 0, 0))
        self.sidebar = sidebar
        sidebar.grid(row=0, column=1, rowspan=2, sticky="nsew")
        sidebar.columnconfigure(0, weight=1)
        sidebar.rowconfigure(4, weight=1)
        sidebar.rowconfigure(6, weight=1)

        self._title_label = ttk.Label(
            sidebar,
            textvariable=window._title_var,
            font=("TkDefaultFont", 12, "bold"),
            justify=tk.LEFT,
            anchor=tk.W,
            # width=1 keeps the label from requesting its full single-line text
            # width, which would otherwise widen the sidebar column for longer
            # titles and shift the board.
            width=1,
        )
        self._title_label.grid(row=0, column=0, sticky="ew")
        self._build_info_grid(sidebar)
        sidebar.bind("<Configure>", lambda event: self._update_sidebar_wraplength(event.width))

        practice_row = ttk.Frame(sidebar)
        practice_row.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        practice_row.columnconfigure(0, weight=1)
        practice_row.columnconfigure(1, weight=0)

        self._build_training_tools(practice_row)

        ttk.Label(sidebar, text="Comment").grid(row=3, column=0, sticky="w")
        self.comment_view = tk.Text(
            sidebar,
            height=4,
            wrap=tk.WORD,
            relief=tk.FLAT,
            borderwidth=1,
            font="TkDefaultFont",
        )
        self.comment_view.grid(row=4, column=0, sticky="nsew", pady=(2, 0))
        window._replace_text(self.comment_view, "")

        self.user_notes_frame = ttk.Frame(sidebar)
        self.user_notes_frame.grid(row=5, column=0, rowspan=2, sticky="nsew", pady=(8, 0))
        self.user_notes_frame.columnconfigure(0, weight=1)
        self.user_notes_frame.rowconfigure(1, weight=1)
        ttk.Label(self.user_notes_frame, text="My Notes").grid(row=0, column=0, sticky="w")
        self.user_note_view = tk.Text(
            self.user_notes_frame,
            height=5,
            wrap=tk.WORD,
            relief=tk.FLAT,
            borderwidth=1,
            font="TkDefaultFont",
            undo=True,
        )
        self.user_note_view.grid(row=1, column=0, sticky="nsew", pady=(2, 0))
        self.user_note_view.bind("<<Modified>>", lambda _event: window.on_user_note_changed())
        if not window._show_user_notes_var.get():
            self.user_notes_frame.grid_remove()
            self.sidebar.rowconfigure(6, weight=0)

    def _build_info_grid(self, sidebar: ttk.Frame) -> None:
        window = self.window
        info = ttk.Frame(sidebar)
        info.grid(row=1, column=0, sticky="ew", pady=(4, 8))
        info.columnconfigure(1, weight=1)
        for row, key in enumerate(("Puzzle", "Move", "Turn", "Side", "Start", "Theme")):
            ttk.Label(info, text=key).grid(row=row, column=0, sticky="w", padx=(0, 12))
            ttk.Label(info, textvariable=window._info_vars[key], font=self._bold_font).grid(
                row=row, column=1, sticky="w"
            )
        self.move_progress_bar = ttk.Progressbar(info, maximum=1.0, variable=window._move_progress)
        self.move_progress_bar.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(6, 0))

    def _build_session_stats(self, parent: ttk.Frame) -> None:
        window = self.window
        stats = ttk.Frame(parent, style="Panel.TFrame")
        self._session_stats_frame = stats
        self._session_stats_grid = {"row": 0, "column": 1, "sticky": "e", "padx": (12, 0)}
        labels = (("Attempted", "Attempted"), ("Solved", "Solved"), ("Total", "Total"), ("Avg", "Average"))
        for column, (label, key) in enumerate(labels):
            value_column = column * 2 + 1
            ttk.Label(stats, text=f"{label}:", style="Panel.TLabel").grid(
                row=0, column=value_column - 1, sticky="e", padx=(0, 2)
            )
            ttk.Label(stats, textvariable=window._session_stats_vars[key], font=self._bold_font).grid(
                row=0, column=value_column, sticky="w", padx=(0, 10)
            )
        # A flat clickable label, not a Button: keeps the status bar one text-line
        # tall so toggling the stats does not change the bar's height.
        reset = ttk.Label(stats, text="⟳", style="Panel.TLabel", cursor="hand2")
        reset.grid(row=0, column=len(labels) * 2, sticky="e")
        reset.bind("<Button-1>", lambda _event: window.reset_session_stats())
        self._tooltips.append(
            ThemedTooltip(reset, "Reset session stats", lambda: self.window.theme_service.current)
        )
        self.set_session_stats_visible(window._show_session_stats_var.get())

    def set_session_stats_visible(self, visible: bool) -> None:
        if visible:
            self._session_stats_frame.grid(**self._session_stats_grid)
        else:
            self._session_stats_frame.grid_remove()

    def _build_welcome_panel(self, shell: ttk.Frame) -> None:
        window = self.window
        self.welcome_frame = ttk.Frame(shell, padding=24)
        ttk.Label(self.welcome_frame, text="Chess Puzzles Trainer", font=("TkDefaultFont", 14, "bold")).pack(
            pady=(0, 4)
        )
        ttk.Label(self.welcome_frame, text="Choose a course to start training.").pack(pady=(0, 14))
        primary_actions = (
            ("Course Library...", window.open_course_library),
            ("Open Course File...", window.open_database),
            ("Add Course...", window.add_course),
        )
        for text, command in primary_actions:
            ttk.Button(
                self.welcome_frame,
                text=text,
                command=self._with_board_focus(command),
                takefocus=False,
            ).pack(fill=tk.X, pady=2)
        self.set_welcome_visible(True)

    def set_welcome_visible(self, visible: bool) -> None:
        if visible:
            self.board_frame.grid_remove()
            self.sidebar.grid_remove()
            self.navigation.grid_remove()
            self.set_session_stats_visible(False)
            self.welcome_frame.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        else:
            self.welcome_frame.place_forget()
            self.board_frame.grid()
            self.sidebar.grid()
            self.navigation.grid()
            self.set_session_stats_visible(self.window._show_session_stats_var.get())

    def _build_training_tools(self, practice_row: ttk.Frame) -> None:
        window = self.window
        training_tools = ttk.LabelFrame(practice_row, text="Training", padding=(6, 4))
        training_tools.grid(row=0, column=0, sticky="nsew")
        training_tools.columnconfigure(0, weight=1)
        training_tools.columnconfigure(1, weight=1)
        skip_first_checkbox = ttk.Checkbutton(
            training_tools,
            text="Skip first move",
            variable=window._skip_first_var,
            command=self._with_board_focus(window.toggle_current_skip),
            takefocus=False,
        )
        skip_first_checkbox.grid(row=0, column=0, sticky="w", padx=(0, 4), pady=(0, 1))
        auto_next_checkbox = ttk.Checkbutton(
            training_tools,
            text="Auto next",
            variable=window._auto_next_var,
            command=self._with_board_focus(window.save_training_preferences),
            takefocus=False,
        )
        auto_next_checkbox.grid(row=0, column=1, sticky="w", pady=(0, 1))
        clean_comments_checkbox = ttk.Checkbutton(
            training_tools,
            text="Clean comments",
            variable=window._clean_comments_var,
            command=self._with_board_focus(window.on_clean_comments_changed),
            takefocus=False,
        )
        clean_comments_checkbox.grid(row=1, column=0, sticky="w", padx=(0, 4))
        pause_for_comment_checkbox = ttk.Checkbutton(
            training_tools,
            text="Pause for comment",
            variable=window._pause_for_comment_var,
            command=self._with_board_focus(window.save_training_preferences),
            takefocus=False,
        )
        pause_for_comment_checkbox.grid(row=1, column=1, sticky="w")

    def _build_status_bar(self) -> None:
        window = self.window
        status = ttk.Frame(window.root, style="Panel.TFrame", padding=(12, 6))
        status.grid(row=1, column=0, sticky="ew")
        status.columnconfigure(0, weight=1)
        ttk.Label(status, textvariable=window._status_var, style="Panel.TLabel").grid(row=0, column=0, sticky="w")
        self._build_session_stats(status)

    def _with_board_focus(self, command: Callable[[], None]) -> Callable[[], None]:
        """Run a control's command, then hand focus back to the board.

        Buttons that keep keyboard focus also respond to Tk's built-in
        space-activates-widget binding, so a later Ctrl+Space (or any
        space-containing shortcut) would re-press them as a side effect.
        """

        def invoke() -> None:
            command()
            self.board.focus_set()

        return invoke

    def _toolbar_button(
        self,
        parent: tk.Misc,
        text: str,
        command: Callable[[], None],
        icon_name: str,
        shortcut: str | None = None,
    ) -> ttk.Button:
        icon = self._load_button_icon(icon_name) if icon_name else None
        button = ttk.Button(
            parent,
            text="" if icon is not None else text,
            command=self._with_board_focus(command),
            takefocus=False,
        )
        if icon is not None:
            button.configure(image=icon)
            self._button_icon_names[button] = icon_name
        button.pack(side=tk.LEFT, padx=(0, 4))
        if shortcut:
            self._add_tooltip(button, text, shortcut)
        return button

    def _add_tooltip(self, widget: tk.Widget, text: str, shortcut: str) -> None:
        shortcut_text = MENU_ACCELERATORS.get(shortcut, shortcut)
        self._tooltips.append(
            ThemedTooltip(widget, f"{text} [{shortcut_text}]", lambda: self.window.theme_service.current)
        )

    def _load_button_icon(self, name: str) -> tk.PhotoImage | None:
        if not name:
            return None
        path = assets_dir() / "img" / "buttons" / name
        if not path.exists():
            return None
        icon = self._button_icons.image_for(path, self.window.theme_service.current.text)
        if icon is not None:
            return icon
        try:
            return tk.PhotoImage(file=str(path))
        except tk.TclError:
            return None

    def refresh_button_icons(self) -> None:
        for button, icon_name in self._button_icon_names.items():
            icon = self._load_button_icon(icon_name)
            if icon is not None:
                button.configure(image=icon, text="")

    def apply_tooltip_theme(self) -> None:
        for tooltip in self._tooltips:
            tooltip.apply_theme()

    def set_toolbar_button_icon(self, button: ttk.Button, icon_name: str, fallback_text: str) -> None:
        icon = self._load_button_icon(icon_name)
        if icon is not None:
            self._button_icon_names[button] = icon_name
            button.configure(image=icon, text="")
        else:
            self._button_icon_names.pop(button, None)
            button.configure(image="", text=fallback_text)

    def _update_sidebar_wraplength(self, width: int) -> None:
        self._title_label.configure(wraplength=max(180, width - 12))
