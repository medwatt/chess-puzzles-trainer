from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import tkinter as tk

    from chess_puzzles.app.main_window import MainWindow


class MainUserNotes:
    def __init__(self, window: MainWindow) -> None:
        self.window = window
        self._save_after_id: str | None = None
        self._loading = False

    def toggle(self) -> None:
        visible = bool(self.window._show_user_notes_var.get())
        self.apply_visibility()
        self.window.save_settings(show_user_notes=visible)

    def apply_visibility(self) -> None:
        window = self.window
        layout = window._layout
        if window._show_user_notes_var.get():
            layout.user_notes_frame.grid()
            layout.sidebar.rowconfigure(4, weight=1)
            layout.sidebar.rowconfigure(6, weight=1)
        else:
            layout.user_notes_frame.grid_remove()
            layout.sidebar.rowconfigure(4, weight=1)
            layout.sidebar.rowconfigure(6, weight=0)

    def on_changed(self) -> None:
        window = self.window
        layout = window._layout
        layout.user_note_view.edit_modified(False)
        if self._loading or window.session is None:
            return
        note = layout.user_note_view.get("1.0", "end-1c")
        if note == window.user_store.get_note(window.session.puzzle.puzzle_id):
            return
        self._schedule_save()

    def load_current(self) -> None:
        window = self.window
        if window.session is None:
            return
        self._loading = True
        try:
            text = window.user_store.get_note(window.session.puzzle.puzzle_id)
            self._replace_text(window._layout.user_note_view, text)
        finally:
            self._loading = False

    def clear(self) -> None:
        self._replace_text(self.window._layout.user_note_view, "")

    def _replace_text(self, widget: tk.Text, text: str) -> None:
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.edit_modified(False)

    def _schedule_save(self) -> None:
        if self._save_after_id is not None:
            self.window.root.after_cancel(self._save_after_id)
        self._save_after_id = self.window.root.after(800, self.save_now)

    def save_now(self) -> None:
        if self._save_after_id is not None:
            self.window.root.after_cancel(self._save_after_id)
            self._save_after_id = None
        window = self.window
        if window.session is None:
            return
        text = window._layout.user_note_view.get("1.0", "end-1c")
        window.user_store.set_note(window.session.puzzle.puzzle_id, text)
