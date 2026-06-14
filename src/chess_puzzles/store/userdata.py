from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from chess_puzzles.platform.paths import user_data_dir
from chess_puzzles.store.clock import now_iso
from chess_puzzles.store.sql import USER_SCHEMA_SQL, VISION_SCHEMA_SQL

# Migration N (index N) upgrades the database from user_version N to N+1. A fresh
# file is at version 0, so migration 0 creates the current schema. To change the
# schema, append a new statement here -- never edit or reorder existing entries.
_USER_MIGRATIONS: tuple[str, ...] = (
    USER_SCHEMA_SQL,
    VISION_SCHEMA_SQL,
)


def _migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version > len(_USER_MIGRATIONS):
        raise ValueError("userdata.db was created by a newer version of the app")
    for target in range(version, len(_USER_MIGRATIONS)):
        conn.executescript(_USER_MIGRATIONS[target])
        conn.execute(f"PRAGMA user_version = {target + 1}")


@dataclass(frozen=True, slots=True)
class Attempt:
    puzzle_id: str
    at: str
    outcome: str
    mistakes: int
    aids: int
    grade: str
    duration_ms: int | None = None


@dataclass(frozen=True, slots=True)
class FavoriteRef:
    puzzle_id: str
    database_id: str
    database_path: str


@dataclass(frozen=True, slots=True)
class VisionAttempt:
    drill_id: str
    at: str
    fen: str
    orientation: int  # chess.Color as 1 (white) / 0 (black)
    answer: str  # comma-separated square indices
    clicks: str  # comma-separated square indices
    tp: int
    fp: int
    fn: int
    passed: bool
    elapsed_ms: int


class UserStore:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    @classmethod
    def open_default(cls) -> "UserStore":
        directory = user_data_dir()
        directory.mkdir(parents=True, exist_ok=True)
        return cls.open(directory / "userdata.db")

    @classmethod
    def open(cls, path: str | Path) -> "UserStore":
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        _migrate(conn)
        return cls(conn)

    def close(self) -> None:
        self._conn.close()

    def record_attempt(self, a: Attempt) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO attempt (puzzle_id, at, outcome, mistakes, aids, duration_ms, grade)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (a.puzzle_id, a.at, a.outcome, a.mistakes, a.aids, a.duration_ms, a.grade),
            )

    def record_vision_attempt(self, a: VisionAttempt) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO vision_attempt"
                " (drill_id, at, fen, orientation, answer, clicks, tp, fp, fn, passed, elapsed_ms)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    a.drill_id,
                    a.at,
                    a.fen,
                    a.orientation,
                    a.answer,
                    a.clicks,
                    a.tp,
                    a.fp,
                    a.fn,
                    int(a.passed),
                    a.elapsed_ms,
                ),
            )

    def get_note(self, puzzle_id: str) -> str:
        row = self._conn.execute("SELECT text FROM note WHERE puzzle_id = ?", (puzzle_id,)).fetchone()
        return row["text"] if row is not None else ""

    def set_note(self, puzzle_id: str, text: str) -> None:
        with self._conn:
            if not text.strip():
                self._conn.execute("DELETE FROM note WHERE puzzle_id = ?", (puzzle_id,))
                return
            self._conn.execute(
                "INSERT INTO note (puzzle_id, text, updated_at) VALUES (?, ?, ?)"
                " ON CONFLICT(puzzle_id) DO UPDATE SET text = excluded.text, updated_at = excluded.updated_at",
                (puzzle_id, text, now_iso()),
            )

    def is_favorite(self, puzzle_id: str, database_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM favorite WHERE puzzle_id = ? AND database_id = ?", (puzzle_id, database_id)
        ).fetchone()
        return row is not None

    def add_favorite(self, puzzle_id: str, database_id: str, database_path: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO favorite (puzzle_id, database_id, database_path, added_at) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(puzzle_id, database_id) DO UPDATE SET"
                " database_path = excluded.database_path, added_at = excluded.added_at",
                (puzzle_id, database_id, database_path, now_iso()),
            )

    def remove_favorite(self, puzzle_id: str, database_id: str) -> None:
        with self._conn:
            self._conn.execute(
                "DELETE FROM favorite WHERE puzzle_id = ? AND database_id = ?", (puzzle_id, database_id)
            )

    def favorite_ids(self, database_id: str) -> set[str]:
        rows = self._conn.execute("SELECT puzzle_id FROM favorite WHERE database_id = ?", (database_id,))
        return {row["puzzle_id"] for row in rows}

    def favorite_refs(self) -> list[FavoriteRef]:
        rows = self._conn.execute(
            "SELECT puzzle_id, database_id, database_path FROM favorite ORDER BY added_at, database_id, puzzle_id"
        )
        return [
            FavoriteRef(row["puzzle_id"], row["database_id"], row["database_path"])
            for row in rows
        ]

    def update_favorite_database_path(self, database_id: str, database_path: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE favorite SET database_path = ? WHERE database_id = ?", (database_path, database_id)
            )

    def get_ui(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM ui_state WHERE key = ?", (key,)).fetchone()
        return row["value"] if row is not None else None

    def set_ui(self, key: str, value: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO ui_state (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
