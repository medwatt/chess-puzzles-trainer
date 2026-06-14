from __future__ import annotations

import os
import shlex
import subprocess
import sys
from dataclasses import dataclass

import chess
import chess.engine

from chess_puzzles.engine.config import EngineDefinition
from chess_puzzles.engine.evaluation import EngineScore, score_from_pov


def split_engine_command(command: str) -> list[str]:
    """Turn a configured engine command into argv.

    A bare executable path is used as-is, so neither Windows backslashes nor
    spaces force the user to add quotes. Only commands with arguments are
    tokenised, and then with the platform's quoting rules (POSIX backslash
    escapes off on Windows).
    """
    command = command.strip()
    if os.path.isfile(command):
        return [command]
    return shlex.split(command, posix=os.name != "nt")


@dataclass(frozen=True, slots=True)
class EngineAnalysis:
    score: EngineScore | None
    best_move: chess.Move | None
    depth: int | None


class UciEngine:
    """Thin wrapper around python-chess' UCI process API."""

    def __init__(self, definition: EngineDefinition) -> None:
        self.definition = definition
        self._engine: chess.engine.SimpleEngine | None = None

    def start(self) -> None:
        if self._engine is not None:
            return
        command = split_engine_command(self.definition.command)
        self._engine = chess.engine.SimpleEngine.popen_uci(command, **self._popen_kwargs())
        options = dict(self.definition.options)
        if "Threads" in self._engine.options:
            options.setdefault("Threads", self.definition.threads)
        if options:
            self._engine.configure(options)

    def analyse(self, board: chess.Board) -> EngineAnalysis:
        if self._engine is None:
            self.start()
        if self._engine is None:
            raise RuntimeError("Engine did not start")
        limit = chess.engine.Limit(time=self.definition.time_limit_seconds, depth=self.definition.depth)
        info = self._engine.analyse(board, limit)
        score = info.get("score")
        pv = info.get("pv") or []
        return EngineAnalysis(
            score=score_from_pov(score) if isinstance(score, chess.engine.PovScore) else None,
            best_move=pv[0] if pv else None,
            depth=info.get("depth") if isinstance(info.get("depth"), int) else None,
        )

    def quit(self) -> None:
        engine = self._engine
        self._engine = None
        if engine is not None:
            engine.quit()

    @staticmethod
    def _popen_kwargs() -> dict[str, object]:
        if sys.platform != "win32":
            return {}
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        return {
            "startupinfo": startupinfo,
            "creationflags": subprocess.CREATE_NO_WINDOW,
        }
