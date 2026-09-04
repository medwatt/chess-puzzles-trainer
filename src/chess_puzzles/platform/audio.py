from __future__ import annotations

import queue
import shutil
import subprocess
import sys
import threading
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
    """Deliver move sounds off the UI thread, in the order requested.

    Command-line audio players are deliberately run by one worker instead of
    being launched concurrently. This gives every accepted event one playback
    attempt, prevents overlapping processes from turning one short cue into
    noisy or unreliable output, and lets us fall back when a backend exits
    unsuccessfully.
    """

    def __init__(self, audio_directory: str | Path | None = None, enabled: bool = False) -> None:
        self.audio_directory = (
            Path(audio_directory) if audio_directory is not None else assets_dir() / "audio"
        )
        self.enabled = enabled
        self._uses_windows_sound = sys.platform == "win32"
        self._play_commands = self._resolve_commands()
        self._preferred_command = 0
        self._requests: queue.Queue[Path | None] = queue.Queue()
        self._closed = False
        self._worker = threading.Thread(
            target=self._playback_worker,
            name="chess-puzzles-audio",
            daemon=True,
        )
        self._worker.start()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def play_move(self, board_before: chess.Board, move: chess.Move, board_after: chess.Board) -> None:
        if self.enabled:
            self._enqueue(sound_key_for_move(board_before, move, board_after))

    def play_error(self) -> None:
        if self.enabled:
            self._enqueue("move")

    def close(self) -> None:
        """Stop accepting sounds and let any active short cue finish."""
        if self._closed:
            return
        self._closed = True
        self.enabled = False
        self._requests.put(None)
        self._worker.join(timeout=0.5)

    def _enqueue(self, sound_key: str) -> None:
        path = self.audio_directory / SOUND_FILES[sound_key]
        if not self._closed and path.exists():
            self._requests.put(path)

    def _playback_worker(self) -> None:
        while True:
            path = self._requests.get()
            try:
                if path is None:
                    return
                if not self._closed:
                    self._play_file(path)
            finally:
                self._requests.task_done()

    def _play_file(self, path: Path) -> None:
        if self._uses_windows_sound:
            try:
                import winsound  # pyright: ignore[reportMissingModuleSource]

                # Synchronous inside the worker: the UI remains asynchronous,
                # while consecutive requests cannot interrupt one another.
                # Windows-only module: on a Linux/macOS type-check its members
                # are genuinely absent, and this branch never runs there.
                winsound.PlaySound(  # pyright: ignore[reportAttributeAccessIssue]
                    str(path),
                    winsound.SND_FILENAME | winsound.SND_NODEFAULT,  # pyright: ignore[reportAttributeAccessIssue]
                )
            except Exception:
                pass
            return

        command_count = len(self._play_commands)
        for offset in range(command_count):
            index = (self._preferred_command + offset) % command_count
            command = self._play_commands[index]
            try:
                result = subprocess.run(
                    (*command, str(path)),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                continue
            if result.returncode == 0:
                self._preferred_command = index
                return

    def _resolve_commands(self) -> tuple[tuple[str, ...], ...]:
        if self._uses_windows_sound:
            return ()
        if sys.platform == "darwin":
            afplay = shutil.which("afplay")
            return ((afplay,),) if afplay else ()

        commands: list[tuple[str, ...]] = []
        # Prefer the desktop sound server's native client. In particular,
        # PulseAudio-on-PipeWire can mix this stream with paused media players
        # without ffplay's decoder/device startup path.
        if paplay := shutil.which("paplay"):
            commands.append(
                (
                    paplay,
                    "--client-name=Chess Puzzles Trainer",
                    "--stream-name=Move sound",
                )
            )
        if ffplay := shutil.which("ffplay"):
            commands.append((ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet"))
        if aplay := shutil.which("aplay"):
            commands.append((aplay,))
        return tuple(commands)


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
