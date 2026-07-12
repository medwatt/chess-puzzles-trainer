"""Persistent course index and incremental filesystem reconciliation."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from chess_puzzles.store.clock import now_iso
from chess_puzzles.store.content import ContentDatabase


@dataclass(frozen=True, slots=True)
class LibraryCourse:
    database_id: str
    name: str
    description: str
    kind: str
    puzzle_count: int
    chapter_count: int
    pinned: bool
    status: str
    path: str
    available: bool
    duplicate_locations: int
    tags: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ScanResult:
    discovered: int = 0
    indexed: int = 0
    unchanged: int = 0
    invalid: int = 0


class CourseLibrary:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def set_root(self, path: str | Path) -> None:
        """Use the configured database folder as the one library root."""
        normalized = str(Path(path).expanduser().resolve())
        with self._conn:
            self._conn.execute("DELETE FROM library_root")
            self._conn.execute(
                "INSERT INTO library_root(path, recursive) VALUES (?, 1)", (normalized,)
            )

    def courses(self) -> list[LibraryCourse]:
        rows = self._conn.execute(
            "SELECT c.*, l.path, COALESCE(l.available, 0) AS available,"
            " (SELECT COUNT(*) FROM library_location d WHERE d.database_id=c.database_id AND d.available=1) AS duplicates,"
            " COALESCE((SELECT GROUP_CONCAT(t.name, ', ') FROM library_course_tag ct"
            " JOIN library_tag t ON t.tag_id=ct.tag_id WHERE ct.database_id=c.database_id), '') AS tags"
            " FROM library_course c LEFT JOIN library_location l ON l.path=("
            " SELECT path FROM library_location x WHERE x.database_id=c.database_id"
            " ORDER BY x.available DESC, x.path LIMIT 1)"
            " ORDER BY c.pinned DESC, c.name COLLATE NOCASE"
        )
        return [
            LibraryCourse(
                row["database_id"], row["name"], row["description"], row["kind"],
                row["puzzle_count"], row["chapter_count"], bool(row["pinned"]), row["status"],
                row["path"] or "", bool(row["available"]), row["duplicates"],
                tuple(tag.strip() for tag in row["tags"].split(",") if tag.strip()),
            )
            for row in rows
        ]

    def resolve_path(self, database_id: str, fallback: str = "") -> Path | None:
        rows = self._conn.execute(
            "SELECT path FROM library_location WHERE database_id=? AND available=1"
            " ORDER BY path", (database_id,)
        ).fetchall()
        if len(rows) == 1 and Path(rows[0][0]).is_file():
            return Path(rows[0][0])
        candidate = Path(fallback) if fallback else None
        return candidate if candidate is not None and candidate.is_file() else None

    def available_paths(self, database_id: str) -> list[Path]:
        rows = self._conn.execute(
            "SELECT path FROM library_location WHERE database_id=? AND available=1 ORDER BY path",
            (database_id,),
        )
        return [Path(row[0]) for row in rows if Path(row[0]).is_file()]

    def relocate_known_path(self, old_path: str | Path) -> Path | None:
        """Resolve a stale recent-file path through its previously indexed identity."""
        row = self._conn.execute(
            "SELECT database_id FROM library_location WHERE path=?", (str(Path(old_path).expanduser().resolve()),)
        ).fetchone()
        return self.resolve_path(row[0]) if row is not None else None

    def register(self, path: str | Path, database: ContentDatabase | None = None) -> None:
        path = Path(path).expanduser().resolve()
        stat = path.stat()
        owned = database is None
        db = database or ContentDatabase.open(path)
        try:
            meta = db.meta
            database_id = db.database_id
            if not database_id:
                raise ValueError("course database has no database_id")
            stamp = now_iso()
            with self._conn:
                self._conn.execute(
                    "INSERT INTO library_course(database_id,name,description,kind,puzzle_count,chapter_count,added_at,indexed_at)"
                    " VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(database_id) DO UPDATE SET"
                    " name=excluded.name, description=excluded.description, kind=excluded.kind,"
                    " puzzle_count=excluded.puzzle_count, chapter_count=excluded.chapter_count, indexed_at=excluded.indexed_at",
                    (database_id, meta.name, meta.description, db.kind, db.count(), len(db.themes()), stamp, stamp),
                )
                self._conn.execute(
                    "INSERT INTO library_location(path,database_id,mtime_ns,file_size,available) VALUES (?,?,?,?,1)"
                    " ON CONFLICT(path) DO UPDATE SET database_id=excluded.database_id,"
                    " mtime_ns=excluded.mtime_ns,file_size=excluded.file_size,available=1",
                    (str(path), database_id, stat.st_mtime_ns, stat.st_size),
                )
        finally:
            if owned:
                db.close()

    def scan(self) -> ScanResult:
        with self._conn:
            self._conn.execute("UPDATE library_location SET available=0")
        discovered = indexed = unchanged = invalid = 0
        for root_row in self._conn.execute("SELECT path, recursive FROM library_root ORDER BY path"):
            root = Path(root_row["path"])
            if not root.is_dir():
                continue
            paths = root.rglob("*.cpdb") if root_row["recursive"] else root.glob("*.cpdb")
            for path in paths:
                discovered += 1
                try:
                    resolved = path.resolve()
                    stat = resolved.stat()
                    row = self._conn.execute(
                        "SELECT mtime_ns,file_size FROM library_location WHERE path=?", (str(resolved),)
                    ).fetchone()
                    if row is not None and row["mtime_ns"] == stat.st_mtime_ns and row["file_size"] == stat.st_size:
                        with self._conn:
                            self._conn.execute(
                                "UPDATE library_location SET available=1 WHERE path=?", (str(resolved),)
                            )
                        unchanged += 1
                        continue
                    self.register(resolved)
                    indexed += 1
                except (OSError, sqlite3.DatabaseError, ValueError):
                    invalid += 1
        return ScanResult(discovered, indexed, unchanged, invalid)

    def set_pinned(self, database_id: str, pinned: bool) -> None:
        with self._conn:
            self._conn.execute("UPDATE library_course SET pinned=? WHERE database_id=?", (int(pinned), database_id))

    def set_status(self, database_id: str, status: str) -> None:
        if status not in {"active", "paused", "completed", "archived"}:
            raise ValueError(f"unsupported course status: {status}")
        with self._conn:
            self._conn.execute("UPDATE library_course SET status=? WHERE database_id=?", (status, database_id))

    def set_tags(self, database_id: str, tags: list[str]) -> None:
        clean = sorted({tag.strip() for tag in tags if tag.strip()}, key=str.casefold)
        with self._conn:
            self._conn.execute("DELETE FROM library_course_tag WHERE database_id=?", (database_id,))
            for tag in clean:
                self._conn.execute("INSERT INTO library_tag(name) VALUES (?) ON CONFLICT(name) DO NOTHING", (tag,))
                self._conn.execute(
                    "INSERT INTO library_course_tag(database_id,tag_id)"
                    " SELECT ?,tag_id FROM library_tag WHERE name=? COLLATE NOCASE",
                    (database_id, tag),
                )
            self._conn.execute(
                "DELETE FROM library_tag WHERE NOT EXISTS ("
                " SELECT 1 FROM library_course_tag ct WHERE ct.tag_id=library_tag.tag_id)"
            )
