"""Modal progress window that runs the blunder miner on a worker thread.

Engine analysis of hundreds of positions takes tens of seconds, far too long
to block the Tk main loop the way the Lichess CSV import does. The worker
thread owns the engine process for its whole life; the dialog polls a queue
for progress and outcome. Cancel (or closing the window) stops the scan at
the next row and *keeps* whatever was accepted so far -- a half-generated
deck is still a deck.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import chess.engine

from chess_puzzles.mining.blunder_miner import BlunderMiner, MinedPuzzle, MiningCriteria


_POLL_MS = 100


class MiningRunDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        engine_command: str,
        engine_threads: int,
        engine_options: dict | None,
        csv_path: Path,
        count: int,
        criteria: MiningCriteria,
    ) -> None:
        super().__init__(parent, name="miningrun", class_="ChessPuzzlesMiningRun")
        self.title("Generating blunder puzzles...")
        self.transient(parent)
        self.resizable(False, False)
        self.result: list[MinedPuzzle] | None = None

        self._engine_command = engine_command
        self._engine_threads = engine_threads
        self._engine_options = dict(engine_options or {})
        self._csv_path = csv_path
        self._count = count
        self._criteria = criteria
        self._queue: queue.Queue[tuple] = queue.Queue()
        self._cancelled = False

        body = ttk.Frame(self, padding=16)
        body.pack(fill=tk.BOTH, expand=True)
        self._progress_var = tk.StringVar(value="Starting engine...")
        ttk.Label(body, textvariable=self._progress_var, width=48).pack(anchor="w")
        self._bar = ttk.Progressbar(body, mode="determinate", maximum=count, length=360)
        self._bar.pack(fill=tk.X, pady=(8, 12))
        ttk.Button(body, text="Stop & keep results", command=self._cancel).pack(anchor="e")

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _event: self._cancel())

        threading.Thread(target=self._worker, daemon=True).start()
        self.after(_POLL_MS, self._poll)

    def show_modal(self) -> list[MinedPuzzle] | None:
        self.grab_set()
        self.wait_window()
        return self.result

    def _cancel(self) -> None:
        self._cancelled = True
        self._progress_var.set("Stopping...")

    def _worker(self) -> None:
        try:
            engine = chess.engine.SimpleEngine.popen_uci(self._engine_command)
        except Exception as exc:
            self._queue.put(("error", f"Could not start the engine:\n{exc}"))
            return
        try:
            options = {**self._engine_options, "Threads": self._engine_threads}
            engine.configure(options)
            miner = BlunderMiner(engine, self._criteria)
            mined = miner.mine(
                self._csv_path,
                self._count,
                on_progress=lambda examined, accepted: self._queue.put(("progress", examined, accepted)),
                should_stop=lambda: self._cancelled,
            )
            self._queue.put(("done", mined))
        except Exception as exc:
            self._queue.put(("error", str(exc)))
        finally:
            try:
                engine.quit()
            except Exception:
                pass

    def _poll(self) -> None:
        outcome = None
        while True:
            try:
                message = self._queue.get_nowait()
            except queue.Empty:
                break
            if message[0] == "progress":
                _, examined, accepted = message
                self._progress_var.set(f"Examined {examined} positions - accepted {accepted} of {self._count}")
                self._bar["value"] = accepted
            else:
                outcome = message
        if outcome is None:
            self.after(_POLL_MS, self._poll)
            return
        if outcome[0] == "error":
            messagebox.showerror("Generation failed", outcome[1], parent=self)
            self.result = None
        else:
            self.result = outcome[1]
        self.destroy()
