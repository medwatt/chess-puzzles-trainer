from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import chess

from chess_puzzles.app.main_window import MainWindow
from chess_puzzles.platform.audio import AudioPlayer
from chess_puzzles.puzzle import Puzzle, PuzzleSession


class _RecordingAudio:
    def __init__(self) -> None:
        self.moves: list[chess.Move] = []

    def play_move(self, _board_before, move, _board_after) -> None:
        self.moves.append(move)


def test_normal_puzzle_move_emits_exactly_one_sound() -> None:
    move = chess.Move.from_uci("e2e4")
    window = MainWindow.__new__(MainWindow)
    window.session = PuzzleSession(
        Puzzle(
            title="ordinary puzzle",
            initial_fen=chess.STARTING_FEN,
            moves=(move, chess.Move.from_uci("e7e5")),
        ),
        chess.WHITE,
    )
    window._refutation_playback = SimpleNamespace(active=False)
    window._engaged = False
    window.audio = _RecordingAudio()
    window._layout = SimpleNamespace(
        board=SimpleNamespace(flash_move=lambda *_args: None)
    )
    window._refresh_from_session = lambda *_args, **_kwargs: None
    window._schedule_computer_reply = lambda: None

    window.on_move_requested(move, animate=False)

    assert window.audio.moves == [move]


def test_linux_prefers_native_sound_server_over_ffplay(monkeypatch) -> None:
    paths = {
        "paplay": "/usr/bin/paplay",
        "ffplay": "/usr/bin/ffplay",
        "aplay": "/usr/bin/aplay",
    }
    monkeypatch.setattr("chess_puzzles.platform.audio.sys.platform", "linux")
    monkeypatch.setattr(
        "chess_puzzles.platform.audio.shutil.which", lambda command: paths.get(command)
    )

    player = AudioPlayer(enabled=False)
    try:
        assert [Path(command[0]).name for command in player._play_commands] == [
            "paplay",
            "ffplay",
            "aplay",
        ]
    finally:
        player.close()


def test_failed_backend_falls_through_and_remembers_success(tmp_path: Path, monkeypatch) -> None:
    player = AudioPlayer(audio_directory=tmp_path, enabled=False)
    player._play_commands = (("native-player",), ("fallback-player",))
    calls: list[str] = []

    def run(command, **_kwargs):
        calls.append(command[0])
        return SimpleNamespace(returncode=1 if command[0] == "native-player" else 0)

    monkeypatch.setattr("chess_puzzles.platform.audio.subprocess.run", run)
    try:
        player._play_file(tmp_path / "move.wav")
        player._play_file(tmp_path / "capture.wav")
    finally:
        player.close()

    assert calls == ["native-player", "fallback-player", "fallback-player"]


def test_each_queued_event_is_played_once_and_in_order(tmp_path: Path, monkeypatch) -> None:
    for filename in ("move.wav", "capture.wav", "check.wav"):
        (tmp_path / filename).touch()

    played: list[str] = []
    monkeypatch.setattr(AudioPlayer, "_play_file", lambda _self, path: played.append(path.name))
    player = AudioPlayer(audio_directory=tmp_path, enabled=True)
    try:
        player._enqueue("move")
        player._enqueue("capture")
        player._enqueue("check")
        player._requests.join()
    finally:
        player.close()

    assert played == ["move.wav", "capture.wav", "check.wav"]
