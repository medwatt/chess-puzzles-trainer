"""Persistence of board-vision preferences, focused on per-drill options.

Options are stored as JSON-native underlying values (bool / number / enum code)
keyed by drill id then option key; load drops anything malformed so a stale file
can't crash.
"""

from __future__ import annotations

import json

from chess_puzzles.vision.settings import (
    VisionSettings,
    load_vision_settings,
    save_vision_settings,
)


def test_drill_options_round_trip(tmp_path) -> None:
    path = tmp_path / "vision.json"
    settings = VisionSettings(
        last_drill_id="hanging",
        timer_seconds=10,
        drill_options={"hanging": {"include_pawns": True, "scope": "opponent", "negative_rate": 0.25}},
    )
    save_vision_settings(settings, path)

    loaded = load_vision_settings(path)
    assert loaded == settings
    assert loaded.drill_options["hanging"]["scope"] == "opponent"
    assert loaded.drill_options["hanging"]["negative_rate"] == 0.25


def test_load_drops_malformed_drill_options(tmp_path) -> None:
    path = tmp_path / "vision.json"
    path.write_text(
        json.dumps(
            {
                "last_drill_id": "reach",
                "drill_options": {
                    "reach": {"include_defended_squares": False, "bad": [1, 2]},
                    "broken": "not-an-object",
                },
            }
        ),
        encoding="utf-8",
    )

    loaded = load_vision_settings(path)
    assert loaded.drill_options == {"reach": {"include_defended_squares": False}}


def test_missing_file_defaults_to_empty_options(tmp_path) -> None:
    loaded = load_vision_settings(tmp_path / "absent.json")
    assert loaded.drill_options == {}
