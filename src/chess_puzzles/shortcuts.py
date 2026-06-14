from __future__ import annotations

import tkinter as tk
from collections.abc import Callable


def event_originates_from_editable(event: tk.Event) -> bool:
    widget = event.widget
    if not isinstance(widget, tk.Widget):
        return False
    widget_class = widget.winfo_class()
    if widget_class in {"Entry", "TEntry", "Spinbox", "TSpinbox", "Combobox", "TCombobox"}:
        return True
    if widget_class != "Text":
        return False
    try:
        return str(widget.cget("state")) != tk.DISABLED
    except tk.TclError:
        return True


def guarded_shortcut(action: Callable[[], None]) -> Callable[[tk.Event], str | None]:
    def handler(event: tk.Event) -> str | None:
        if event_originates_from_editable(event):
            return None
        action()
        return "break"

    return handler


class Shortcut(str):
    """A Tk bind sequence that also carries help metadata.

    Behaves like a plain string for binding and dictionary lookups, but
    stores a human-readable label and section. This way defining a
    shortcut also registers it in Help > Keyboard Shortcuts, so there is
    no second list to keep in sync.
    """

    label: str
    section: str

    def __new__(cls, sequence: str, label: str, section: str) -> "Shortcut":
        obj = super().__new__(cls, sequence)
        obj.label = label
        obj.section = section
        return obj


# Help-dialog sections. They appear in the order of first shortcut that
# references them, since that matches how the sections are grouped below.
TRAINING = "Training"
BOARD = "Board & insights"
ENGINE = "Engine"
DATABASE = "Database & files"
APPLICATION = "Application"
MANAGER = "Database manager"


class MainShortcuts:
    """Shortcuts owned by the main window.

    Bare letters are current-puzzle board/training actions. Ctrl+letter
    opens primary commands and modes. Ctrl+Shift+letter is reserved for
    persistent toggles, secondary variants, exports, and preferences.
    """

    # Training
    NEXT_PUZZLE = Shortcut("<Right>", "Next puzzle", TRAINING)
    PREVIOUS_PUZZLE = Shortcut("<Left>", "Previous puzzle", TRAINING)
    RESET_PUZZLE = Shortcut("r", "Reset puzzle", TRAINING)
    SHOW_HINT = Shortcut("h", "Show hint", TRAINING)
    PLAY_MOVE = Shortcut("m", "Play move for me", TRAINING)
    GO_TO_PUZZLE = Shortcut("<Control-g>", "Go to puzzle...", TRAINING)
    START_THEME = Shortcut("<Control-t>", "Start theme...", TRAINING)
    TOGGLE_SKIP = Shortcut("<Control-Shift-K>", "Toggle skip first move", TRAINING)
    TOGGLE_AUTO_NEXT = Shortcut("<Control-Shift-A>", "Toggle auto next", TRAINING)
    TOGGLE_CLEAN_COMMENTS = Shortcut("<Control-Shift-L>", "Toggle clean comments", TRAINING)
    BOARD_VISION = Shortcut("<Control-v>", "Board vision", TRAINING)

    # Board & insights
    FLIP_BOARD = Shortcut("f", "Flip board", BOARD)
    SHOW_THREATS = Shortcut("t", "Show opponent threat", BOARD)
    TOGGLE_HANGING_OVERLAY = Shortcut("d", "Highlight hanging pieces (danger)", BOARD)
    TOGGLE_CONTESTED_OVERLAY = Shortcut("c", "Show contested squares", BOARD)
    CLEAR_MARKS = Shortcut("<Escape>", "Clear marks", BOARD)
    TOGGLE_COORDINATES = Shortcut("<Control-Shift-C>", "Toggle coordinates", BOARD)

    # Engine
    TOGGLE_ENGINE_ANALYSIS = Shortcut("<Control-space>", "Start/pause analysis", ENGINE)
    PLAY_VS_ENGINE = Shortcut("<Control-Shift-E>", "Play vs engine", ENGINE)
    CONFIGURE_ENGINES = Shortcut("<Control-e>", "Configure engines...", ENGINE)
    TOGGLE_EVALUATION_BAR = Shortcut("<Control-Shift-B>", "Toggle evaluation bar", ENGINE)

    # Database & files
    OPEN_DATABASE = Shortcut("<Control-o>", "Open database...", DATABASE)
    NEW_DATABASE_FROM_PGN = Shortcut("<Control-n>", "New from PGN...", DATABASE)
    IMPORT_LICHESS_CSV = Shortcut("<Control-i>", "Import Lichess CSV...", DATABASE)
    EDIT_DATABASE = Shortcut("<Control-m>", "Edit database...", DATABASE)
    SAVE_FAVORITE = Shortcut("<Control-s>", "Save to Favorites", DATABASE)
    DELETE_CURRENT_PUZZLE = Shortcut("<Control-Delete>", "Delete puzzle", DATABASE)
    SHOW_PGN = Shortcut("<Control-p>", "Show PGN viewer", DATABASE)
    COPY_PGN = Shortcut("<Control-Shift-P>", "Copy puzzle PGN", DATABASE)
    COPY_POSITION = Shortcut("<Control-Shift-F>", "Copy position FEN", DATABASE)
    EXPORT_BOARD_SVG = Shortcut("<Control-Shift-S>", "Export board SVG...", DATABASE)

    # Application
    SHOW_SHORTCUTS = Shortcut("?", "Keyboard shortcuts", APPLICATION)
    CHOOSE_FONT = Shortcut("<Control-comma>", "Choose font...", APPLICATION)
    CONFIGURE_FOLDERS = Shortcut("<Control-Shift-D>", "Folders...", APPLICATION)
    EXIT = Shortcut("<Control-q>", "Quit", APPLICATION)


class DatabaseShortcuts:
    """Shortcuts owned by the database manager dialog."""

    DELETE_SELECTED = Shortcut("<Delete>", "Delete selected puzzles", MANAGER)
    SAVE = Shortcut("<Control-s>", "Save and close", MANAGER)
    CANCEL = Shortcut("<Escape>", "Cancel", MANAGER)
    SET_SELECTED_SKIP = Shortcut("<Control-k>", "Set skip on selected", MANAGER)
    CLEAR_SELECTED_SKIP = Shortcut("<Control-Shift-K>", "Clear skip on selected", MANAGER)
    SET_SELECTED_THEME = Shortcut("<Control-t>", "Set theme on selected...", MANAGER)
    CLEAR_SELECTED_THEME = Shortcut("<Control-BackSpace>", "Clear theme on selected", MANAGER)
    SET_THEME_FROM_WHITE = Shortcut("<Control-Shift-W>", "Theme from White header", MANAGER)
    SET_THEME_FROM_BLACK = Shortcut("<Control-Shift-B>", "Theme from Black header", MANAGER)


_KEY_DISPLAY = {
    "control": "Ctrl",
    "shift": "Shift",
    "alt": "Alt",
    "escape": "Esc",
    "delete": "Del",
    "backspace": "Backspace",
    "space": "Space",
    "comma": ",",
}


def accelerator_text(sequence: str) -> str:
    """Human-readable accelerator for a Tk bind sequence."""
    if not sequence.startswith("<"):
        return sequence.upper() if len(sequence) == 1 and sequence.isalpha() else sequence
    parts = []
    for token in sequence.strip("<>").split("-"):
        key = token.lower()
        if key in _KEY_DISPLAY:
            parts.append(_KEY_DISPLAY[key])
        elif len(token) == 1:
            parts.append(token.upper())
        else:
            parts.append(token)
    return "+".join(parts)


def registered_shortcuts(*owners: type) -> list[Shortcut]:
    """All Shortcut declarations on the given classes, in definition order."""
    found: list[Shortcut] = []
    for owner in owners or (MainShortcuts, DatabaseShortcuts):
        found.extend(value for value in vars(owner).values() if isinstance(value, Shortcut))
    return found


def _build_help_sections() -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    grouped: dict[str, list[tuple[str, str]]] = {}
    for shortcut in registered_shortcuts():
        grouped.setdefault(shortcut.section, []).append((shortcut.label, str(shortcut)))
    return tuple((section, tuple(entries)) for section, entries in grouped.items())


# Built from the Shortcut declarations above. The menu accelerator map
# and the Help > Keyboard Shortcuts dialog both read these.
MENU_ACCELERATORS: dict[str, str] = {
    str(shortcut): accelerator_text(shortcut) for shortcut in registered_shortcuts()
}
SHORTCUT_HELP_SECTIONS = _build_help_sections()
