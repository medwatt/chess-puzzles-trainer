"""Modal progress window that scans the Lichess CSV on a worker thread.

The puzzle database is ~1GB and the scan runs until enough rows match, so a
narrow filter can read the whole file: measured at ~28 seconds for a
combination that matches nothing. Doing that on the Tk main loop froze the
app with no progress and no way out, which is exactly why the blunder miner
grew this dialog first -- this is the same shape, without an engine.

Cancel (or closing the window) stops at the next row and keeps whatever
matched so far: a short deck is still a deck.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from chess_puzzles.lichess.importer import LichessCsvImporter, LichessImportCriteria
from chess_puzzles.puzzle import Puzzle
from chess_puzzles.ui.modal import ModalParent, run_modal


_POLL_MS = 100
# The scan reads ~180k rows/second, so reporting every row would flood the
# queue with work the UI cannot use. Roughly ten updates a second is plenty.
_PROGRESS_EVERY = 20_000


class LichessImportRunDialog(tk.Toplevel):
    def __init__(
        self,
        parent: ModalParent,
        *,
        csv_path: Path,
        criteria: LichessImportCriteria,
    ) -> None:
        super().__init__(parent, name="lichessimportrun", class_="ChessPuzzlesLichessImportRun")
        self.title("Searching Lichess puzzles...")
        self.transient(parent)
        self.resizable(False, False)
        self.result: list[Puzzle] | None = None

        self._csv_path = csv_path
        self._criteria = criteria
        self._queue: queue.Queue[tuple] = queue.Queue()
        self._cancelled = False

        body = ttk.Frame(self, padding=16)
        body.pack(fill=tk.BOTH, expand=True)
        self._progress_var = tk.StringVar(value="Scanning...")
        ttk.Label(body, textvariable=self._progress_var, width=52).pack(anchor="w")
        self._bar = ttk.Progressbar(
            body, mode="determinate", maximum=criteria.sample_size, length=380
        )
        self._bar.pack(fill=tk.X, pady=(8, 12))
        ttk.Button(body, text="Stop & keep results", command=self._cancel).pack(anchor="e")

        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda _event: self._cancel())

        threading.Thread(target=self._worker, daemon=True).start()
        self.after(_POLL_MS, self._poll)

    def show_modal(self) -> list[Puzzle] | None:
        run_modal(self)
        return self.result

    def _cancel(self) -> None:
        self._cancelled = True
        self._progress_var.set("Stopping...")

    def _report(self, examined: int, accepted: int) -> None:
        # The completing row almost never lands on a throttle boundary, so it
        # is always sent: otherwise the bar stops just short of the total.
        if examined % _PROGRESS_EVERY == 0 or accepted >= self._criteria.sample_size:
            self._queue.put(("progress", examined, accepted))

    def _worker(self) -> None:
        try:
            puzzles = LichessCsvImporter().sample_puzzles(
                self._csv_path,
                self._criteria,
                on_progress=self._report,
                should_stop=lambda: self._cancelled,
            )
            self._queue.put(("done", puzzles))
        except Exception as exc:
            self._queue.put(("error", str(exc)))

    def _poll(self) -> None:
        outcome = None
        while True:
            try:
                message = self._queue.get_nowait()
            except queue.Empty:
                break
            if message[0] == "progress":
                _, examined, accepted = message
                self._progress_var.set(
                    f"Searched {examined:,} puzzles - found {accepted} of {self._criteria.sample_size}"
                )
                self._bar["value"] = accepted
            else:
                outcome = message
        if outcome is None:
            self.after(_POLL_MS, self._poll)
            return
        if outcome[0] == "error":
            messagebox.showerror("Could not import Lichess CSV", outcome[1], parent=self)
            self.result = None
        else:
            self.result = outcome[1]
        self.destroy()
