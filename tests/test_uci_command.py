from __future__ import annotations

import os
from pathlib import Path

import pytest

from chess_puzzles.engine.uci import split_engine_command


def test_existing_path_is_used_as_is(tmp_path: Path) -> None:
    # A real path with a space: must not be split, with or without quotes.
    binary = tmp_path / "my engine.exe"
    binary.write_text("", encoding="utf-8")
    assert split_engine_command(str(binary)) == [str(binary)]
    assert split_engine_command(f"  {binary}  ") == [str(binary)]


def test_command_with_arguments_is_tokenised() -> None:
    assert split_engine_command("stockfish --threads 2") == ["stockfish", "--threads", "2"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX backslash handling")
def test_posix_backslashes_still_escape_when_not_a_file() -> None:
    # Non-existent path falls back to shlex; POSIX rules apply on non-Windows.
    assert split_engine_command("/usr/bin/stockfish") == ["/usr/bin/stockfish"]
