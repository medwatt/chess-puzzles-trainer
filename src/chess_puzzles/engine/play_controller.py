from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Literal

import chess

from chess_puzzles.engine.config import EngineDefinition
from chess_puzzles.engine.evaluation import EngineScore
from chess_puzzles.engine.uci import EngineAnalysis
from chess_puzzles.engine.worker import drain_queue, run_engine_worker


@dataclass(frozen=True, slots=True)
class EngineMoveResult:
    request_id: int
    kind: Literal["analyse", "move"]
    move: chess.Move | None
    score: EngineScore | None = None
    error: str = ""


@dataclass(frozen=True, slots=True)
class _Request:
    kind: Literal["analyse", "move", "stop"]
    request_id: int = 0
    board: chess.Board | None = None


class EnginePlayController:
    """Background best-move + analysis controller used by the play-vs-engine window."""

    def __init__(self, definition: EngineDefinition) -> None:
        self.definition = definition
        self._request_id = 0
        self._request_queue: queue.Queue[_Request] = queue.Queue()
        self._result_queue: queue.Queue[EngineMoveResult] = queue.Queue()
        self._thread = threading.Thread(
            target=run_engine_worker,
            args=(definition, self._request_queue, self._result_queue),
            kwargs={"on_analysis": self._on_analysis, "on_error": self._on_error},
            daemon=True,
        )
        self._thread.start()

    @property
    def request_id(self) -> int:
        return self._request_id

    def request_move(self, board: chess.Board) -> int:
        self._request_id += 1
        self._request_queue.put(_Request("move", self._request_id, board.copy(stack=False)))
        return self._request_id

    def request_analysis(self, board: chess.Board) -> int:
        self._request_id += 1
        self._request_queue.put(_Request("analyse", self._request_id, board.copy(stack=False)))
        return self._request_id

    def cancel_pending(self) -> None:
        self._request_id += 1

    def get_pending_results(self) -> list[EngineMoveResult]:
        return drain_queue(self._result_queue)

    def shutdown(self) -> None:
        self.cancel_pending()
        self._request_queue.put(_Request("stop"))

    @staticmethod
    def _on_analysis(request: _Request, analysis: EngineAnalysis) -> EngineMoveResult:
        return EngineMoveResult(
            request_id=request.request_id,
            kind=request.kind,
            move=analysis.best_move,
            score=analysis.score,
        )

    @staticmethod
    def _on_error(request: _Request, exc: Exception) -> EngineMoveResult:
        return EngineMoveResult(request.request_id, request.kind, None, error=str(exc))
