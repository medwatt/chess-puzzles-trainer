from __future__ import annotations

import pytest

from chess_puzzles.json_config import load_json_object, save_json_object


def test_save_and_load_round_trip(tmp_path) -> None:
    path = tmp_path / "nested" / "data.json"
    data = {"name": "test", "values": [1, 2, 3]}

    save_json_object(path, data)

    assert load_json_object(path, error_message="bad") == data


def test_save_leaves_no_temporary_file(tmp_path) -> None:
    path = tmp_path / "data.json"

    save_json_object(path, {"key": "value"})

    assert [entry.name for entry in tmp_path.iterdir()] == ["data.json"]


def test_failed_save_keeps_previous_file_intact(tmp_path, monkeypatch) -> None:
    path = tmp_path / "data.json"
    save_json_object(path, {"key": "old"})

    monkeypatch.setattr("chess_puzzles.json_config.os.replace", _raise_os_error)
    with pytest.raises(OSError):
        save_json_object(path, {"key": "new"})

    assert load_json_object(path, error_message="bad") == {"key": "old"}
    assert [entry.name for entry in tmp_path.iterdir()] == ["data.json"]


def test_load_rejects_non_object_json(tmp_path) -> None:
    path = tmp_path / "data.json"
    path.write_text("[1, 2]", encoding="utf-8")

    with pytest.raises(ValueError, match="bad"):
        load_json_object(path, error_message="bad")


def _raise_os_error(*_args: object) -> None:
    raise OSError("simulated write failure")
