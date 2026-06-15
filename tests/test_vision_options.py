"""Unit tests for the pure value-mapping core of the options panel.

The Tk widgets are exercised manually; these cover the reflective label<->value
mapping that used to be inline (and untested) in the window.
"""

from __future__ import annotations

from chess_puzzles.vision.analysis import ColorScope
from chess_puzzles.vision.drill import DrillOption
from chess_puzzles.vision.options_panel import (
    initial_label,
    resolve_option_value,
    storage_value,
    stored_label,
)

_SCOPE = DrillOption(
    "scope",
    "Pieces",
    (("Both", ColorScope.BOTH), ("Side to move", ColorScope.SIDE_TO_MOVE)),
)
_TOGGLE = DrillOption("include_pawns", "Include pawns")
_NEGATIVES = DrillOption("negative_rate", "Negatives", (("Off", 0.0), ("Sometimes", 0.25)))


def test_resolve_choice_option_maps_label_to_value() -> None:
    assert resolve_option_value(_SCOPE, "Side to move") is ColorScope.SIDE_TO_MOVE
    assert resolve_option_value(_NEGATIVES, "Sometimes") == 0.25


def test_resolve_boolean_option_coerces_widget_state() -> None:
    assert resolve_option_value(_TOGGLE, True) is True
    assert resolve_option_value(_TOGGLE, 0) is False


def test_initial_label_matches_current_value() -> None:
    assert initial_label(_SCOPE, ColorScope.SIDE_TO_MOVE) == "Side to move"
    assert initial_label(_NEGATIVES, 0.0) == "Off"


def test_initial_label_falls_back_to_first_choice() -> None:
    assert initial_label(_SCOPE, ColorScope.OPPONENT) == "Both"


def test_storage_value_serializes_underlying_value_not_label() -> None:
    assert storage_value(_SCOPE, "Side to move") == "side_to_move"  # enum code, not label
    assert storage_value(_NEGATIVES, "Sometimes") == 0.25
    assert storage_value(_TOGGLE, True) is True


def test_stored_label_round_trips_storage_value() -> None:
    assert stored_label(_SCOPE, "side_to_move", ColorScope.BOTH) == "Side to move"
    assert stored_label(_NEGATIVES, 0.25, 0.0) == "Sometimes"


def test_stored_label_falls_back_when_value_unknown() -> None:
    # A stored code no longer present in the choices yields the current value's label.
    assert stored_label(_SCOPE, "opponent", ColorScope.SIDE_TO_MOVE) == "Side to move"
