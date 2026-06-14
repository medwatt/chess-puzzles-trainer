from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk

from chess_puzzles.constants import DEFAULT_UI_THEME_ID
from chess_puzzles.settings.theme_repository import UiTheme, built_in_ui_themes


ThemeListener = Callable[[UiTheme], None]


class ThemeService:
    def __init__(self, root: tk.Tk, theme_id: str = DEFAULT_UI_THEME_ID) -> None:
        self.root = root
        self.themes = built_in_ui_themes()
        self.current = self.themes.get(theme_id, self.themes[DEFAULT_UI_THEME_ID])
        self._listeners: list[ThemeListener] = []
        self._style = ttk.Style(root)
        self.apply(self.current.id)

    def add_listener(self, listener: ThemeListener) -> None:
        self._listeners.append(listener)
        listener(self.current)

    def apply(self, theme_id: str) -> UiTheme:
        self.current = self.themes.get(theme_id, self.themes[DEFAULT_UI_THEME_ID])
        self._apply_ttk(self.current)
        self._apply_tk_defaults(self.current)
        for listener in tuple(self._listeners):
            listener(self.current)
        return self.current

    def _apply_ttk(self, theme: UiTheme) -> None:
        try:
            self._style.theme_use("clam")
        except tk.TclError:
            pass

        # The "." style is the catch-all root. Every ttk widget class
        # inherits these colours and state maps unless a specific class
        # overrides them. This means menubuttons, scrollbars, the file
        # dialog, and any widget we add later all follow the theme.
        self._style.configure(
            ".",
            background=theme.window_bg,
            foreground=theme.text,
            bordercolor=theme.border,
            darkcolor=theme.border,
            lightcolor=theme.button_bg,
            troughcolor=theme.sunken_bg,
            fieldbackground=theme.field_bg,
            selectbackground=theme.menu_active_bg,
            selectforeground=theme.menu_active_text,
            insertcolor=theme.field_text,
            arrowcolor=theme.text,
            focuscolor=theme.accent,
        )
        self._style.map(
            ".",
            background=[("active", theme.button_active), ("pressed", theme.button_active)],
            foreground=[("disabled", theme.muted_text)],
            fieldbackground=[("readonly", theme.field_bg), ("disabled", theme.sunken_bg)],
            # clam dims unfocused selection with hardcoded gray. Use a
            # muted theme colour so it matches the current palette.
            selectbackground=[("!focus", theme.border)],
            selectforeground=[("!focus", theme.text)],
        )
        self._style.configure("TFrame", background=theme.window_bg)
        self._style.configure("Panel.TFrame", background=theme.panel_bg)
        self._style.configure("Sunken.TFrame", background=theme.sunken_bg)
        self._style.configure("TLabel", background=theme.window_bg, foreground=theme.text)
        self._style.configure("Panel.TLabel", background=theme.panel_bg, foreground=theme.text)
        self._style.configure("Muted.TLabel", background=theme.window_bg, foreground=theme.muted_text)
        self._style.configure("MutedPanel.TLabel", background=theme.panel_bg, foreground=theme.muted_text)
        self._style.configure(
            "TButton",
            background=theme.button_bg,
            foreground=theme.text,
            bordercolor=theme.border,
            focusthickness=1,
            focuscolor=theme.accent,
            padding=(10, 6),
        )
        self._style.map(
            "TButton",
            background=[("active", theme.button_active), ("pressed", theme.button_active)],
            foreground=[("disabled", theme.muted_text)],
        )
        self._style.configure(
            "TCheckbutton",
            background=theme.window_bg,
            foreground=theme.text,
            focuscolor=theme.accent,
        )
        self._style.map("TCheckbutton", background=[("active", theme.window_bg)])
        self._style.configure(
            "TRadiobutton",
            background=theme.window_bg,
            foreground=theme.text,
            focuscolor=theme.accent,
        )
        self._style.map("TRadiobutton", background=[("active", theme.window_bg)])
        self._style.configure(
            "TEntry",
            fieldbackground=theme.field_bg,
            foreground=theme.field_text,
            bordercolor=theme.border,
            insertcolor=theme.field_text,
            selectbackground=theme.menu_active_bg,
            selectforeground=theme.menu_active_text,
        )
        self._style.configure(
            "TMenubutton",
            background=theme.button_bg,
            foreground=theme.text,
            bordercolor=theme.border,
        )
        self._style.configure(
            "TScrollbar",
            background=theme.button_bg,
            troughcolor=theme.sunken_bg,
            bordercolor=theme.border,
            arrowcolor=theme.text,
        )
        self._style.map("TScrollbar", background=[("active", theme.button_active)])
        self._style.configure(
            "TCombobox",
            fieldbackground=theme.field_bg,
            background=theme.button_bg,
            foreground=theme.field_text,
            bordercolor=theme.border,
            arrowcolor=theme.text,
            selectbackground=theme.field_bg,
            selectforeground=theme.field_text,
        )
        self._style.map(
            "TCombobox",
            fieldbackground=[("readonly", theme.field_bg), ("disabled", theme.field_bg)],
            foreground=[("readonly", theme.field_text), ("disabled", theme.muted_text)],
            background=[("active", theme.button_active)],
        )
        self._style.configure(
            "Horizontal.TScale",
            background=theme.button_bg,
            troughcolor=theme.sunken_bg,
            bordercolor=theme.border,
            lightcolor=theme.button_bg,
            darkcolor=theme.border,
            gripcount=0,
        )
        self._style.map("Horizontal.TScale", background=[("active", theme.button_active)])
        self._style.configure(
            "TSpinbox",
            fieldbackground=theme.field_bg,
            background=theme.button_bg,
            foreground=theme.field_text,
            bordercolor=theme.border,
            arrowcolor=theme.text,
            insertcolor=theme.field_text,
            selectbackground=theme.menu_active_bg,
            selectforeground=theme.menu_active_text,
        )
        self._style.configure(
            "Treeview",
            background=theme.field_bg,
            fieldbackground=theme.field_bg,
            foreground=theme.field_text,
            bordercolor=theme.border,
        )
        # menu_active_bg + menu_active_text is the one curated readable
        # pair in every theme. accent alone can collide with light text
        # (e.g. in Gruvbox).
        self._style.map(
            "Treeview",
            background=[("selected", theme.menu_active_bg)],
            foreground=[("selected", theme.menu_active_text)],
        )
        self._style.configure(
            "Horizontal.TProgressbar",
            background=theme.accent,
            troughcolor=theme.sunken_bg,
            bordercolor=theme.border,
            lightcolor=theme.accent,
            darkcolor=theme.accent,
            thickness=6,
        )
        self._style.configure(
            "Treeview.Heading",
            background=theme.button_bg,
            foreground=theme.text,
            bordercolor=theme.border,
            relief="flat",
        )
        self._style.map(
            "Treeview.Heading",
            background=[("active", theme.button_active)],
        )

    def _apply_tk_defaults(self, theme: UiTheme) -> None:
        self.root.configure(bg=theme.window_bg)
        self.root.option_add("*Background", theme.window_bg)
        self.root.option_add("*Foreground", theme.text)
        self.root.option_add("*Menu.background", theme.menu_bg)
        self.root.option_add("*Menu.foreground", theme.text)
        self.root.option_add("*Menu.activeBackground", theme.menu_active_bg)
        self.root.option_add("*Menu.activeForeground", theme.menu_active_text)
        self.root.option_add("*Menu.selectColor", theme.accent)
        self.root.option_add("*Entry.background", theme.field_bg)
        self.root.option_add("*Entry.foreground", theme.field_text)
        self.root.option_add("*Listbox.background", theme.field_bg)
        self.root.option_add("*Listbox.foreground", theme.field_text)
        self.root.option_add("*Listbox.selectBackground", theme.menu_active_bg)
        self.root.option_add("*Listbox.selectForeground", theme.menu_active_text)
        self.root.option_add("*Listbox.highlightBackground", theme.border)
        self.root.option_add("*Listbox.highlightColor", theme.accent)
        self.root.option_add("*TCombobox*Listbox.background", theme.field_bg)
        self.root.option_add("*TCombobox*Listbox.foreground", theme.field_text)
        self.root.option_add("*TCombobox*Listbox.selectBackground", theme.menu_active_bg)
        self.root.option_add("*TCombobox*Listbox.selectForeground", theme.menu_active_text)
        self.root.option_add("*Text.background", theme.field_bg)
        self.root.option_add("*Text.foreground", theme.field_text)
        self.root.option_add("*Text.highlightBackground", theme.border)
        self.root.option_add("*Text.highlightColor", theme.accent)
        self.root.option_add("*Text.insertBackground", theme.field_text)
        self.root.option_add("*Text.selectBackground", theme.menu_active_bg)
        self.root.option_add("*Text.selectForeground", theme.menu_active_text)
