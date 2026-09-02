from __future__ import annotations

from pathlib import Path

import chess

from chess_puzzles.puzzle import Puzzle
from chess_puzzles.store import Attempt, ContentDatabase, ContentMeta, UserStore, now_iso


def _course(path: Path, database_id: str = "course-1", name: str = "Course") -> None:
    db = ContentDatabase.create(
        path,
        ContentMeta(database_id=database_id, name=name),
        [Puzzle(title="One", initial_fen=chess.STARTING_FEN, moves=())],
    )
    db.close()


def test_scan_indexes_new_files_and_skips_unchanged(tmp_path: Path) -> None:
    root = tmp_path / "courses"
    root.mkdir()
    _course(root / "one.cpdb")
    store = UserStore.open(tmp_path / "user.db")
    store.library.set_root(root)

    first = store.library.scan()
    second = store.library.scan()

    assert first.indexed == 1
    assert second.unchanged == 1
    course = store.library.courses()[0]
    assert course.name == "Course"
    assert course.available


def test_moved_course_keeps_identity_tags_and_pin(tmp_path: Path) -> None:
    root = tmp_path / "courses"
    first_dir, second_dir = root / "first", root / "second"
    first_dir.mkdir(parents=True)
    second_dir.mkdir()
    original = first_dir / "course.cpdb"
    moved = second_dir / "renamed.cpdb"
    _course(original)
    store = UserStore.open(tmp_path / "user.db")
    store.library.set_root(root)
    store.library.scan()
    store.library.set_pinned("course-1", True)
    store.library.set_tags("course-1", ["Calculation", "Advanced"])
    store.library.set_status("course-1", "paused")

    original.rename(moved)
    store.library.scan()

    course = store.library.courses()[0]
    assert course.pinned
    assert course.status == "paused"
    assert set(course.tags) == {"Calculation", "Advanced"}
    assert store.library.resolve_path("course-1") == moved.resolve()
    assert store.library.relocate_known_path(original) == moved.resolve()


def test_duplicate_identity_is_reported_and_missing_course_is_retained(tmp_path: Path) -> None:
    root = tmp_path / "courses"
    root.mkdir()
    first, second = root / "one.cpdb", root / "copy.cpdb"
    _course(first)
    _course(second)
    store = UserStore.open(tmp_path / "user.db")
    store.library.set_root(root)
    store.library.scan()

    assert store.library.courses()[0].duplicate_locations == 2
    assert store.library.resolve_path("course-1") is None
    assert store.library.available_paths("course-1") == sorted((first.resolve(), second.resolve()))

    first.unlink()
    second.unlink()
    store.library.scan()
    course = store.library.courses()[0]
    assert not course.available
    assert course.database_id == "course-1"


def test_forgetting_a_course_whose_file_remains_does_not_stick(tmp_path: Path) -> None:
    # Why removal has to delete the file: the library dialog rescans every
    # time it opens, and a scan re-indexes anything still on disk.
    root = tmp_path / "courses"
    root.mkdir()
    _course(root / "one.cpdb")
    store = UserStore.open(tmp_path / "user.db")
    store.library.set_root(root)
    store.library.scan()

    store.library.forget("course-1")
    assert store.library.courses() == []

    store.library.scan()
    assert [course.name for course in store.library.courses()] == ["Course"]


def test_forgetting_a_missing_course_survives_a_rescan(tmp_path: Path) -> None:
    root = tmp_path / "courses"
    root.mkdir()
    path = root / "one.cpdb"
    _course(path)
    store = UserStore.open(tmp_path / "user.db")
    store.library.set_root(root)
    store.library.scan()
    path.unlink()
    store.library.scan()
    assert not store.library.courses()[0].available

    store.library.forget("course-1")
    store.library.scan()

    assert store.library.courses() == []


def test_forgetting_a_course_keeps_the_attempt_history(tmp_path: Path) -> None:
    # The library index is a view over files; the training record is not.
    root = tmp_path / "courses"
    root.mkdir()
    _course(root / "one.cpdb")
    store = UserStore.open(tmp_path / "user.db")
    store.library.set_root(root)
    store.library.scan()
    store.record_attempt(
        Attempt(
            puzzle_id="p1",
            at=now_iso(),
            outcome="solved",
            mistakes=0,
            aids=0,
            grade="good",
            duration_ms=1000,
            database_id="course-1",
            database_path=str(root / "one.cpdb"),
        )
    )

    store.library.forget("course-1")

    rows = store.connection.execute("SELECT COUNT(*) FROM attempt").fetchone()
    assert rows[0] == 1
