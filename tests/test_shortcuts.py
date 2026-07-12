from __future__ import annotations

from chess_puzzles.shortcuts import (
    MENU_ACCELERATORS,
    SHORTCUT_HELP_SECTIONS,
    DatabaseShortcuts,
    MainShortcuts,
    accelerator_text,
    registered_shortcuts,
)


def test_every_shortcut_is_in_the_help_dialog_and_accelerator_map() -> None:
    listed = {sequence for _section, entries in SHORTCUT_HELP_SECTIONS for _label, sequence in entries}
    for shortcut in registered_shortcuts():
        assert str(shortcut) in listed, f"{shortcut.label} missing from help sections"
        assert str(shortcut) in MENU_ACCELERATORS, f"{shortcut.label} missing from accelerators"


def test_no_conflicting_sequences_within_a_window() -> None:
    for owner in (MainShortcuts, DatabaseShortcuts):
        sequences = [str(shortcut) for shortcut in registered_shortcuts(owner)]
        duplicates = {sequence for sequence in sequences if sequences.count(sequence) > 1}
        assert not duplicates, f"{owner.__name__} binds the same sequence twice: {duplicates}"


def test_every_shortcut_has_label_and_section() -> None:
    for shortcut in registered_shortcuts():
        assert shortcut.label.strip()
        assert shortcut.section.strip()


def test_accelerator_text_formats() -> None:
    assert accelerator_text("<Control-Shift-O>") == "Ctrl+Shift+O"
    assert accelerator_text("<Control-KeyPress-1>") == "Ctrl+1"
    assert accelerator_text("<Control-comma>") == "Ctrl+,"
    assert accelerator_text("<Control-Delete>") == "Ctrl+Del"
    assert accelerator_text("<Control-space>") == "Ctrl+Space"
    assert accelerator_text("<Control-BackSpace>") == "Ctrl+Backspace"
    assert accelerator_text("<Escape>") == "Esc"
    assert accelerator_text("<Left>") == "Left"
    assert accelerator_text("f") == "F"
    assert accelerator_text("?") == "?"
