from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import chess

from chess_puzzles.platform.paths import assets_dir


SOUND_FILES = {
    "move": "move.wav",
    "capture": "capture.wav",
    "castle": "castle.wav",
    "check": "check.wav",
    "checkmate": "checkmate.wav",
}


class AudioPlayer:
    def __init__(self, audio_directory: str | Path | None = None, enabled: bool = False) -> None:
        self.audio_directory = Path(audio_directory) if audio_directory is not None else assets_dir() / "audio"
        self.enabled = enabled
        self._playbacks: list[subprocess.Popen[bytes]] = []
        self._uses_windows_sound = sys.platform == "win32"
        self._play_command = self._resolve_command()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def play_move(self, board_before: chess.Board, move: chess.Move, board_after: chess.Board) -> None:
        if self.enabled:
            self._play(sound_key_for_move(board_before, move, board_after))

    def play_error(self) -> None:
        if self.enabled:
            self._play("move")

    def _play(self, sound_key: str) -> None:
        path = self.audio_directory / SOUND_FILES[sound_key]
        if not path.exists():
            return
        if self._uses_windows_sound:
            try:
                import winsound

                winsound.PlaySound(str(path), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
            except Exception:
                return
            return
        if self._play_command is None:
            return
        self._playbacks = [playback for playback in self._playbacks if playback.poll() is None]
        try:
            self._playbacks.append(
                subprocess.Popen(
                    (*self._play_command, str(path)),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            )
        except Exception:
            return

    def _resolve_command(self) -> tuple[str, ...] | None:
        if self._uses_windows_sound:
            return None
        if sys.platform == "darwin":
            afplay = shutil.which("afplay")
            return (afplay,) if afplay else None
        if ffplay := shutil.which("ffplay"):
            return (ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet")
        if paplay := shutil.which("paplay"):
            return (paplay,)
        if aplay := shutil.which("aplay"):
            return (aplay,)
        return None


def sound_key_for_move(board_before: chess.Board, move: chess.Move, board_after: chess.Board) -> str:
    if board_after.is_checkmate():
        return "checkmate"
    if board_after.is_check():
        return "check"
    if board_before.is_castling(move):
        return "castle"
    if board_before.is_capture(move):
        return "capture"
    return "move"
