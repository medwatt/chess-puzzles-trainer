from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Literal

import chess

from chess_puzzles.engine.config import EngineConfig, EngineDefinition
from chess_puzzles.engine.evaluation import EngineScore
from chess_puzzles.engine.uci import EngineAnalysis
from chess_puzzles.engine.worker import drain_queue, run_engine_worker


class EngineState(Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"


AnalysisPurpose = Literal["eval", "threat"]


@dataclass(frozen=True, slots=True)
class EngineResult:
    analysis_id: int
    score: EngineScore | None
    best_move: chess.Move | None
    depth: int | None
    error: str = ""
    purpose: AnalysisPurpose = "eval"


@dataclass(frozen=True, slots=True)
class _Request:
    kind: Literal["analyse", "stop"]
    analysis_id: int = 0
    board: chess.Board | None = None
    purpose: AnalysisPurpose = "eval"


class EngineController:
    """Background analysis controller used by the main board view."""

    def __init__(self, config: EngineConfig) -> None:
        self.config = config
        self.state = EngineState.STOPPED
        self._analysis_id = 0
        self._request_queue: queue.Queue[_Request] = queue.Queue()
        self._result_queue: queue.Queue[EngineResult] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._definition: EngineDefinition | None = None

    @property
    def analysis_id(self) -> int:
        return self._analysis_id

    def set_config(self, config: EngineConfig) -> None:
        self.pause()
        self.config = config

    def start(self) -> str | None:
        definition = self.config.default_engine
        if definition is None:
            self.state = EngineState.ERROR
            return "Configure a default engine first."
        self._definition = definition
        self._ensure_thread(definition)
        self.state = EngineState.RUNNING
        return None

    def pause(self) -> None:
        self._analysis_id += 1
        if self._thread is not None:
            self._request_queue.put(_Request("stop"))
            self._thread.join(timeout=0.1)
        self._thread = None
        self._request_queue = queue.Queue()
        self.state = EngineState.PAUSED

    def shutdown(self) -> None:
        self.pause()
        self.state = EngineState.STOPPED

    def analyse_if_running(self, board: chess.Board | None, purpose: AnalysisPurpose = "eval") -> int:
        if self.state != EngineState.RUNNING or board is None:
            return self._analysis_id
        self._analysis_id += 1
        self._request_queue.put(_Request("analyse", self._analysis_id, board.copy(stack=False), purpose))
        return self._analysis_id

    def get_pending_results(self) -> list[EngineResult]:
        return drain_queue(self._result_queue)

    def _ensure_thread(self, definition: EngineDefinition) -> None:
        if self._thread is not None and self._thread.is_alive() and self._definition == definition:
            return
        if self._thread is not None:
            self.pause()
        self._definition = definition
        self._thread = threading.Thread(
            target=run_engine_worker,
            args=(definition, self._request_queue, self._result_queue),
            kwargs={"on_analysis": self._on_analysis, "on_error": self._on_error},
            daemon=True,
        )
        self._thread.start()

    @staticmethod
    def _on_analysis(request: _Request, analysis: EngineAnalysis) -> EngineResult:
        return EngineResult(
            analysis_id=request.analysis_id,
            score=analysis.score,
            best_move=analysis.best_move,
            depth=analysis.depth,
            purpose=request.purpose,
        )

    @staticmethod
    def _on_error(request: _Request, exc: Exception) -> EngineResult:
        return EngineResult(request.analysis_id, None, None, None, str(exc), request.purpose)
