from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from chess_puzzles.store.userdata import Attempt, UserStore, VisionAttempt
from chess_puzzles.vision.stats import vision_summary

# Bumped whenever a migration is appended to _USER_MIGRATIONS.
CURRENT_USER_VERSION = 3


def _attempt(outcome: str = "solved") -> Attempt:
    return Attempt(
        puzzle_id="p1", at="2026-01-01T00:00:00Z", outcome=outcome,
        mistakes=1, aids=0, grade="hard", duration_ms=4200,
    )


def _vision(drill_id: str = "reach-knight", *, passed: bool = True, elapsed_ms: int = 2000) -> VisionAttempt:
    return VisionAttempt(
        drill_id=drill_id, at="2026-01-01T00:00:00Z", fen="8/8/8/8/8/8/8/8 w - - 0 1",
        orientation=1, answer="1,2,3", clicks="1,2,3", tp=3, fp=0, fn=0,
        passed=passed, elapsed_ms=elapsed_ms,
    )


def _user_version(path: Path) -> int:
    conn = sqlite3.connect(str(path))
    try:
        return conn.execute("PRAGMA user_version").fetchone()[0]
    finally:
        conn.close()


def test_fresh_database_is_at_current_version(tmp_path: Path) -> None:
    path = tmp_path / "u.db"
    UserStore.open(path).close()
    assert _user_version(path) == CURRENT_USER_VERSION


def test_reopen_preserves_data_and_version(tmp_path: Path) -> None:
    path = tmp_path / "u.db"
    store = UserStore.open(path)
    store.record_attempt(_attempt())
    store.close()

    reopened = UserStore.open(path)
    rows = reopened._conn.execute("SELECT COUNT(*) FROM attempt").fetchone()
    assert rows[0] == 1
    assert _user_version(path) == CURRENT_USER_VERSION


def test_database_from_newer_version_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "u.db"
    UserStore.open(path).close()
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA user_version = 99")
    conn.commit()
    conn.close()

    with pytest.raises(ValueError):
        UserStore.open(path)


def test_record_attempt_appends_rows(tmp_path: Path) -> None:
    store = UserStore.open(tmp_path / "u.db")
    store.record_attempt(_attempt())
    store.record_attempt(_attempt("gave_up"))
    rows = store._conn.execute("SELECT puzzle_id, outcome, mistakes FROM attempt ORDER BY id").fetchall()
    assert [tuple(row) for row in rows] == [("p1", "solved", 1), ("p1", "gave_up", 1)]


def test_vision_attempts_and_summary(tmp_path: Path) -> None:
    store = UserStore.open(tmp_path / "u.db")
    store.record_vision_attempt(_vision(passed=True, elapsed_ms=2000))
    store.record_vision_attempt(_vision(passed=False, elapsed_ms=4000))
    store.record_vision_attempt(_vision(drill_id="hanging", passed=True, elapsed_ms=1000))

    overall = vision_summary(store.connection)
    assert overall.trials == 3
    assert overall.passed == 2
    assert overall.total_ms == 7000
    assert overall.average_ms == 2333

    one = vision_summary(store.connection, drill_id="reach-knight")
    assert one.trials == 2
    assert one.passed == 1
    assert round(one.accuracy_percent, 1) == 50.0


def test_notes_set_get_clear(tmp_path: Path) -> None:
    store = UserStore.open(tmp_path / "u.db")
    assert store.get_note("p1") == ""
    store.set_note("p1", "hello")
    assert store.get_note("p1") == "hello"
    store.set_note("p1", "   ")
    assert store.get_note("p1") == ""


def test_favorites(tmp_path: Path) -> None:
    store = UserStore.open(tmp_path / "u.db")
    assert not store.is_favorite("p1", "db1")
    store.add_favorite("p1", "db1", "/tmp/a.cpdb")
    store.add_favorite("p1", "db1", "/tmp/a.cpdb")  # idempotent on id + database
    assert store.is_favorite("p1", "db1")
    assert not store.is_favorite("p1", "db2")
    assert store.favorite_ids("db1") == {"p1"}
    assert store.favorite_ids("db2") == set()
    assert store.favorite_refs()[0].database_path == "/tmp/a.cpdb"
    store.remove_favorite("p1", "db1")
    assert store.favorite_ids("db1") == set()


def test_favorite_path_updates(tmp_path: Path) -> None:
    store = UserStore.open(tmp_path / "u.db")
    store.add_favorite("p1", "db1", "/tmp/old.cpdb")
    store.update_favorite_database_path("db1", "/tmp/new.cpdb")
    assert store.favorite_refs()[0].database_path == "/tmp/new.cpdb"


def test_ui_state_and_persistence(tmp_path: Path) -> None:
    path = tmp_path / "u.db"
    store = UserStore.open(path)
    assert store.get_ui("k") is None
    store.set_ui("k", "v1")
    store.set_ui("k", "v2")
    store.set_note("p1", "kept")
    store.close()

    reopened = UserStore.open(path)
    assert reopened.get_ui("k") == "v2"
    assert reopened.get_note("p1") == "kept"
