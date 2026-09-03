from __future__ import annotations

import chess_puzzles.database.manager as manager
from chess_puzzles.database.manager import DatabaseManagerDialog


class _Table:
    """The slice of ttk.Treeview the theme actions use."""

    def __init__(self, rows: dict[str, list[object]]) -> None:
        self.rows = rows
        self._selection: tuple[str, ...] = ()

    def get_children(self) -> list[str]:
        return list(self.rows)

    def selection(self) -> tuple[str, ...]:
        return self._selection

    def delete(self, row_id: str) -> None:
        del self.rows[row_id]

    def item(self, row_id: str, key: str = "", values: list[object] | None = None):
        if values is not None:
            self.rows[row_id] = list(values)
            return None
        return list(self.rows[row_id])


def _dialog(headers: dict[int, dict[str, str]]) -> DatabaseManagerDialog:
    dialog = DatabaseManagerDialog.__new__(DatabaseManagerDialog)
    dialog._headers = headers
    blank = [""] * len(DatabaseManagerDialog.COLUMNS)
    dialog.table = _Table({str(ordinal): list(blank) for ordinal in headers})
    return dialog


def _themes(dialog: DatabaseManagerDialog) -> list[object]:
    index = DatabaseManagerDialog.COLUMNS.index("theme")
    return [dialog.table.item(row_id)[index] for row_id in dialog.table.get_children()]


class _Var:
    def set(self, value: str) -> None:
        self.value = value


class _Choice:
    """Stand-in for ChoiceDialog that records what it was offered."""

    offered: list[str] = []
    answer: str | None = None

    def __init__(self, parent, title, label, choices, default=None) -> None:
        _Choice.offered = list(choices)
        _Choice.label = label

    def show_modal(self) -> str | None:
        return _Choice.answer


def test_theme_from_tag_fills_selected_rows(monkeypatch) -> None:
    monkeypatch.setattr(manager, "ChoiceDialog", _Choice)
    _Choice.answer = "Pattern"
    dialog = _dialog(
        {
            1: {"Pattern": "Anastasia's mate", "Event": "Warm-up"},
            2: {"Pattern": "Greco's mate", "Event": "Warm-up"},
        }
    )
    dialog.table._selection = ("1",)

    dialog._set_theme_from_tag()

    assert _themes(dialog) == ["Anastasia's mate", ""]
    assert _Choice.offered == ["Event", "Pattern"]


def test_theme_from_tag_without_selection_covers_the_deck(monkeypatch) -> None:
    monkeypatch.setattr(manager, "ChoiceDialog", _Choice)
    _Choice.answer = "Pattern"
    dialog = _dialog({1: {"Pattern": "Hook mate"}, 2: {"Pattern": "Arabian mate"}})

    dialog._set_theme_from_tag()

    assert _themes(dialog) == ["Hook mate", "Arabian mate"]
    assert "all 2" in _Choice.label


def test_theme_from_tag_treats_placeholders_as_empty(monkeypatch) -> None:
    monkeypatch.setattr(manager, "ChoiceDialog", _Choice)
    _Choice.answer = "Black"
    dialog = _dialog({1: {"Black": "?"}, 2: {"Black": " Paul Morphy "}, 3: {"White": "x"}})

    dialog._set_theme_from_tag()

    assert _themes(dialog) == ["", "Paul Morphy", ""]


def test_theme_from_tag_cancelled_leaves_rows_untouched(monkeypatch) -> None:
    monkeypatch.setattr(manager, "ChoiceDialog", _Choice)
    _Choice.answer = None
    dialog = _dialog({1: {"Pattern": "Hook mate"}})

    dialog._set_theme_from_tag()

    assert _themes(dialog) == [""]


def test_deleting_rows_drops_their_headers(monkeypatch) -> None:
    monkeypatch.setattr(manager.messagebox, "askyesno", lambda *args, **kwargs: True)
    dialog = _dialog({1: {"Pattern": "Hook mate"}, 2: {"Pattern": "Arabian mate"}})
    dialog.summary_var = _Var()
    dialog.table._selection = ("1",)

    dialog._delete_selected()

    assert list(dialog._headers) == [2]
