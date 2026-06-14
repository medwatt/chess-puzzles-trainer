from __future__ import annotations

from dataclasses import replace

from chess_puzzles.constants import DEFAULT_PIECE_THEME_ID
from chess_puzzles.settings.model import AppSettings
from chess_puzzles.settings.repository import SettingsRepository
from chess_puzzles.settings.theme_repository import (
    available_piece_themes,
    built_in_board_themes,
    built_in_piece_themes,
    built_in_ui_themes,
)


def test_settings_round_trip(tmp_path) -> None:
    repository = SettingsRepository(tmp_path / "settings.json")
    settings = replace(
        AppSettings(),
        ui_theme_id="dark",
        board_theme_id="blue",
        show_coordinates=False,
        recent_database_paths=("/tmp/a.puzzles",),
    )

    repository.save(settings)

    assert repository.load() == settings


def test_settings_load_partial_json_uses_dataclass_defaults(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text('{"ui_theme_id": "dark"}', encoding="utf-8")

    settings = SettingsRepository(path).load()

    assert settings.ui_theme_id == "dark"
    assert settings.font_size == 10
    assert settings.piece_theme_id == DEFAULT_PIECE_THEME_ID


def test_theme_repositories_include_app_and_board_choices() -> None:
    ui_themes = built_in_ui_themes()
    board_themes = built_in_board_themes()
    piece_themes = built_in_piece_themes()

    assert {
        "light",
        "dark",
        "graphite_light",
        "solarized",
        "nord",
        "gruvbox",
        "dracula",
        "monokai",
    } <= set(ui_themes)
    assert {
        "lightwood3",
        "lichess_brown",
        "lichess_blue",
        "lichess_green",
    } <= set(board_themes)
    assert {"Cburnett", "Merida"} <= set(piece_themes)


def test_user_piece_folder_adds_and_overrides_sets(tmp_path) -> None:
    (tmp_path / "MyPieces").mkdir()
    (tmp_path / "Merida").mkdir()

    themes = available_piece_themes(tmp_path)

    assert "MyPieces" in themes
    assert themes["MyPieces"].image_directory == tmp_path / "MyPieces"
    # A user set named like a bundled one replaces its raster art but keeps
    # the bundled SVG export assets.
    assert themes["Merida"].image_directory == tmp_path / "Merida"
    assert themes["Merida"].svg_directory == built_in_piece_themes()["Merida"].svg_directory
    # Bundled sets the user did not override are still present.
    assert "Cburnett" in themes


def test_missing_user_piece_folder_falls_back_to_built_ins(tmp_path) -> None:
    themes = available_piece_themes(tmp_path / "does-not-exist")

    assert themes == built_in_piece_themes()
