from __future__ import annotations

import dataclasses

from chess_puzzles.settings.model import AppSettings
from chess_puzzles.settings.options import (
    OPTIONS,
    QUICK_OPTIONS,
    SECTIONS,
    options_in,
)
from chess_puzzles.settings.repository import SettingsRepository
from chess_puzzles.store import DECK_KIND_REPERTOIRE, DECK_KIND_TACTICS


def test_every_option_names_a_settings_field() -> None:
    fields = {field.name for field in dataclasses.fields(AppSettings)}
    for option in OPTIONS:
        assert option.key in fields, f"{option.key} has no AppSettings field"


def test_every_option_is_reachable_from_a_section() -> None:
    listed = [option for section in SECTIONS for option in options_in(section)]
    assert listed == list(OPTIONS)


def test_every_option_has_a_label_and_help() -> None:
    for option in OPTIONS:
        assert option.label.strip()
        assert option.help.strip()
        assert not option.label.endswith("."), "labels are names, not sentences"


def test_every_option_is_a_boolean_setting() -> None:
    # The dialog and the sidebar both render checkbuttons, nothing else.
    defaults = AppSettings()
    for option in OPTIONS:
        assert isinstance(getattr(defaults, option.key), bool), option.key


def test_quick_options_exist_and_are_a_subset() -> None:
    assert QUICK_OPTIONS
    assert set(QUICK_OPTIONS) <= set(OPTIONS)


def test_repertoire_options_are_the_only_deck_scoped_ones() -> None:
    scoped = [option for option in OPTIONS if option.kinds is not None]
    assert {option.key for option in scoped} == {
        "start_lines_at_divergence",
        "demonstrate_new_lines",
    }
    for option in scoped:
        assert option.applies_to(DECK_KIND_REPERTOIRE)
        assert not option.applies_to(DECK_KIND_TACTICS)
        assert not option.applies_to(None)


def test_unscoped_options_apply_everywhere_including_no_deck() -> None:
    for option in OPTIONS:
        if option.kinds is None:
            assert option.applies_to(None)
            assert option.applies_to(DECK_KIND_TACTICS)


def _load(tmp_path, payload: str) -> AppSettings:
    path = tmp_path / "settings.json"
    path.write_text(payload, encoding="utf-8")
    return SettingsRepository(path).load()


def test_renamed_keys_are_read_from_their_old_names(tmp_path) -> None:
    settings = _load(
        tmp_path,
        '{"clean_comments": true, "auto_next_enabled": false, "pause_for_comment": false}',
    )

    assert settings.reflow_comments is True
    assert settings.auto_advance is False
    assert settings.stop_at_comments is False


def test_new_names_win_over_the_old_ones(tmp_path) -> None:
    settings = _load(tmp_path, '{"clean_comments": true, "reflow_comments": false}')

    assert settings.reflow_comments is False


def test_step_through_lines_is_read_from_the_old_playback_keys(tmp_path) -> None:
    assert _load(tmp_path, '{"pause_playback_each_move": true}').step_through_lines is True
    assert _load(tmp_path, '{"pause_playback_each_move": false}').step_through_lines is False
    # The short-lived three-way pace collapses the same way.
    assert _load(tmp_path, '{"playback_pace": "every_move"}').step_through_lines is True
    assert _load(tmp_path, '{"playback_pace": "comments"}').step_through_lines is False
    assert _load(tmp_path, '{"playback_pace": "nonsense"}').step_through_lines is False


def test_stopping_at_comments_is_one_setting_for_solving_and_playback(tmp_path) -> None:
    # It replaces pause_for_comment, which already governed both places.
    assert _load(tmp_path, '{"pause_for_comment": true}').stop_at_comments is True
    assert _load(tmp_path, '{"pause_for_comment": false}').stop_at_comments is False


def test_settings_with_no_stored_preferences_use_the_defaults(tmp_path) -> None:
    settings = _load(tmp_path, "{}")

    assert settings.auto_advance is True
    assert settings.stop_at_comments is True
    assert settings.show_avoided_mistakes is True
    assert settings.step_through_lines is False
