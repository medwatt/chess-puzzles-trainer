from __future__ import annotations

import queue
from typing import Callable, Protocol, TypeVar

import chess

from chess_puzzles.engine.config import EngineDefinition
from chess_puzzles.engine.uci import EngineAnalysis, UciEngine


class _BoardRequest(Protocol):
    kind: str
    board: chess.Board | None


Req = TypeVar("Req", bound=_BoardRequest)
Res = TypeVar("Res")


def drain_queue(result_queue: queue.Queue[Res]) -> list[Res]:
    """Return every result currently queued, without blocking."""
    results: list[Res] = []
    while True:
        try:
            results.append(result_queue.get_nowait())
        except queue.Empty:
            return results


def run_engine_worker(
    definition: EngineDefinition,
    request_queue: queue.Queue[Req],
    result_queue: queue.Queue[Res],
    *,
    on_analysis: Callable[[Req, EngineAnalysis], Res],
    on_error: Callable[[Req, Exception], Res],
) -> None:
    """Drive a UCI engine from a request queue until a ``"stop"`` request arrives.

    Requests with no board are ignored. For each board request the engine is
    analysed and the caller-supplied ``on_analysis`` / ``on_error`` callbacks map
    the outcome onto a result that is pushed to ``result_queue``.
    """
    engine = UciEngine(definition)
    try:
        while True:
            request = request_queue.get()
            if request.kind == "stop":
                return
            if request.board is None:
                continue
            try:
                analysis = engine.analyse(request.board)
            except Exception as exc:  # noqa: BLE001 - reported back to the caller as a result
                result_queue.put(on_error(request, exc))
                continue
            result_queue.put(on_analysis(request, analysis))
    finally:
        engine.quit()
