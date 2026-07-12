from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

import chess

from chess_puzzles.puzzle import Puzzle
from chess_puzzles.store.clock import now_iso
from chess_puzzles.store.identity import puzzle_fingerprint
from chess_puzzles.store.sql import CONTENT_SCHEMA_SQL


_META_KEYS = (
    "database_id",
    "name",
    "description",
    "source_kind",
    "source_path",
    "created_at",
    "updated_at",
)

# Deck kinds, stored under the free-form meta key "kind". A deck without the
# key is a tactics deck -- every database created before deck kinds existed
# reads correctly with no migration.
DECK_KIND_TACTICS = "tactics"
DECK_KIND_REPERTOIRE = "repertoire"

_COLOR_TO_TEXT = {chess.WHITE: "white", chess.BLACK: "black"}
_TEXT_TO_COLOR = {"white": chess.WHITE, "black": chess.BLACK}


@dataclass(frozen=True, slots=True)
class ContentMeta:
    database_id: str
    name: str
    description: str = ""
    source_kind: str = "pgn"
    source_path: str = ""
    created_at: str = ""
    updated_at: str = ""


class ContentDatabase:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    @classmethod
    def create(
        cls, path: str | Path, meta: ContentMeta, puzzles: Iterable[Puzzle]
    ) -> "ContentDatabase":
        path = Path(path)
        tmp_path = path.with_name(path.name + ".tmp")
        tmp_path.unlink(missing_ok=True)
        conn = _connect(tmp_path)
        try:
            db = cls._populate(conn, meta, puzzles)
        except Exception:
            conn.close()
            tmp_path.unlink(missing_ok=True)
            raise
        db.close()
        os.replace(tmp_path, path)
        return cls.open(path)

    @classmethod
    def in_memory(cls, meta: ContentMeta, puzzles: Iterable[Puzzle]) -> "ContentDatabase":
        # A transient deck (e.g. the favorites view) that reuses every read/solve
        # path the app already has, without a file on disk.
        return cls._populate(_connect(":memory:"), meta, puzzles)

    @classmethod
    def _populate(
        cls, conn: sqlite3.Connection, meta: ContentMeta, puzzles: Iterable[Puzzle]
    ) -> "ContentDatabase":
        conn.executescript(CONTENT_SCHEMA_SQL)
        with conn:
            conn.executemany(
                "INSERT INTO meta (key, value) VALUES (?, ?)",
                [(key, getattr(meta, key)) for key in _META_KEYS],
            )
            conn.executemany(
                "INSERT INTO puzzle (puzzle_id, ordinal, title, initial_fen, moves, comments, headers,"
                " pgn_text, player_color, skip_first_move, theme, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    _puzzle_to_row(puzzle, ordinal)
                    for ordinal, puzzle in enumerate(puzzles, start=1)
                ),
            )
        return cls(conn)

    @classmethod
    def open(cls, path: str | Path) -> "ContentDatabase":
        conn = _connect(path)
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        if version != 1:
            conn.close()
            raise ValueError("unsupported/old content database")
        return cls(conn)

    def close(self) -> None:
        self._conn.close()

    @property
    def meta(self) -> ContentMeta:
        rows = self._conn.execute("SELECT key, value FROM meta").fetchall()
        values = {row["key"]: row["value"] for row in rows}
        return ContentMeta(**{key: values.get(key, "") or "" for key in _META_KEYS})

    @property
    def database_id(self) -> str:
        row = self._conn.execute("SELECT value FROM meta WHERE key = 'database_id'").fetchone()
        return row["value"] if row is not None else ""

    def set_name(self, name: str) -> None:
        with self._conn:
            self._conn.execute("UPDATE meta SET value = ? WHERE key = 'name'", (name,))
            self._touch()

    def meta_value(self, key: str, default: str = "") -> str:
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row is not None and row["value"] else default

    def set_meta_value(self, key: str, value: str) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
            self._touch()

    @property
    def kind(self) -> str:
        return self.meta_value("kind", DECK_KIND_TACTICS)

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM puzzle").fetchone()[0]

    def puzzle_at(self, index: int) -> Puzzle:
        row = self._conn.execute("SELECT * FROM puzzle WHERE ordinal = ?", (index + 1,)).fetchone()
        if row is None:
            raise IndexError(index)
        return _row_to_puzzle(row)

    def puzzle_by_id(self, puzzle_id: str) -> Puzzle | None:
        row = self._conn.execute(
            "SELECT * FROM puzzle WHERE puzzle_id = ? ORDER BY ordinal LIMIT 1", (puzzle_id,)
        ).fetchone()
        return _row_to_puzzle(row) if row is not None else None

    def index_of_id(self, puzzle_id: str) -> int | None:
        # puzzle_id is not unique (e.g. study pages sharing a position); resolve
        # cross-store lookups (resume-last-puzzle) to the first occurrence.
        row = self._conn.execute(
            "SELECT ordinal FROM puzzle WHERE puzzle_id = ? ORDER BY ordinal LIMIT 1", (puzzle_id,)
        ).fetchone()
        return row["ordinal"] - 1 if row is not None else None

    def iter_puzzles(self) -> Iterator[Puzzle]:
        for row in self._conn.execute("SELECT * FROM puzzle ORDER BY ordinal"):
            yield _row_to_puzzle(row)

    def themes(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT DISTINCT theme FROM puzzle WHERE theme <> '' ORDER BY theme"
        )
        return [row["theme"] for row in rows]

    def theme_position(self, index: int) -> tuple[int, int] | None:
        row = self._conn.execute(
            "SELECT theme, ordinal FROM puzzle WHERE ordinal = ?", (index + 1,)
        ).fetchone()
        if row is None or not row["theme"]:
            return None
        theme, ordinal = row["theme"], row["ordinal"]
        total = self._conn.execute(
            "SELECT COUNT(*) FROM puzzle WHERE theme = ?", (theme,)
        ).fetchone()[0]
        position = self._conn.execute(
            "SELECT COUNT(*) FROM puzzle WHERE theme = ? AND ordinal <= ?", (theme, ordinal)
        ).fetchone()[0]
        return position, total

    def set_skip_first_move(self, ordinal: int, value: bool) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE puzzle SET skip_first_move = ? WHERE ordinal = ?",
                (1 if value else 0, ordinal),
            )
            self._touch()

    def update_puzzles(self, updates: Iterable[tuple[int, bool, str]]) -> None:
        with self._conn:
            self._conn.executemany(
                "UPDATE puzzle SET skip_first_move = ?, theme = ? WHERE ordinal = ?",
                ((1 if skip else 0, theme, ordinal) for ordinal, skip, theme in updates),
            )
            self._touch()

    def delete_puzzles(self, ordinals: Iterable[int]) -> None:
        values = list(ordinals)
        if not values:
            return
        with self._conn:
            self._conn.executemany("DELETE FROM puzzle WHERE ordinal = ?", ((o,) for o in values))
            self._renumber_ordinals()
            self._touch()

    def _renumber_ordinals(self) -> None:
        # Reassign 1..N by current order. New ordinals are always <= the old one
        # (rows only ever shift down after deletes), so updating in ascending
        # order never collides with a not-yet-moved row.
        rows = self._conn.execute("SELECT ordinal FROM puzzle ORDER BY ordinal").fetchall()
        self._conn.executemany(
            "UPDATE puzzle SET ordinal = ? WHERE ordinal = ?",
            ((new, row["ordinal"]) for new, row in enumerate(rows, start=1)),
        )

    def _touch(self) -> None:
        self._conn.execute("UPDATE meta SET value = ? WHERE key = 'updated_at'", (now_iso(),))


def _connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_puzzle(row: sqlite3.Row) -> Puzzle:
    return Puzzle(
        title=row["title"],
        initial_fen=row["initial_fen"],
        moves=tuple(chess.Move.from_uci(uci) for uci in json.loads(row["moves"])),
        comments=tuple(json.loads(row["comments"])),
        headers=json.loads(row["headers"]),
        pgn_text=row["pgn_text"],
        puzzle_id=row["puzzle_id"],
        ordinal=row["ordinal"],
        player_color=_TEXT_TO_COLOR.get(row["player_color"]),
        skip_first_move=bool(row["skip_first_move"]),
        theme=row["theme"],
    )


def _puzzle_to_row(puzzle: Puzzle, ordinal: int) -> tuple:
    moves = [move.uci() for move in puzzle.moves]
    return (
        puzzle.puzzle_id
        or puzzle_fingerprint(puzzle.initial_fen, tuple(moves), tuple(puzzle.comments)),
        ordinal,
        puzzle.title,
        puzzle.initial_fen,
        json.dumps(moves),
        json.dumps(list(puzzle.comments)),
        json.dumps(puzzle.headers),
        puzzle.pgn_text,
        _COLOR_TO_TEXT.get(puzzle.player_color),
        1 if puzzle.skip_first_move else 0,
        puzzle.theme,
        now_iso(),
    )
