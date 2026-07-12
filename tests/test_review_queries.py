from datetime import UTC, datetime

from chess_puzzles.review.queries import due_reviews
from chess_puzzles.store.userdata import Attempt, UserStore


def _attempt(
    puzzle_id: str,
    at: str,
    grade: str,
    *,
    duration_ms: int | None = 1_000,
    database_id: str = "db1",
    database_path: str = "/tmp/deck.cpdb",
) -> Attempt:
    return Attempt(
        puzzle_id=puzzle_id,
        at=at,
        outcome="solved" if grade != "again" else "gave_up",
        mistakes=0,
        aids=0,
        grade=grade,
        duration_ms=duration_ms,
        database_id=database_id,
        database_path=database_path,
    )


def _store(tmp_path) -> UserStore:
    return UserStore.open(tmp_path / "u.db")


_NOW = datetime(2026, 7, 6, tzinfo=UTC)


def test_failed_puzzle_becomes_due_and_clean_one_does_not(tmp_path) -> None:
    store = _store(tmp_path)
    store.record_attempt(_attempt("failed", "2026-07-01T00:00:00Z", "again"))
    store.record_attempt(_attempt("clean", "2026-07-01T00:00:00Z", "easy"))
    due = due_reviews(store.connection, now=_NOW)
    assert [review.puzzle_id for review in due] == ["failed"]
    assert due[0].database_path == "/tmp/deck.cpdb"


def test_not_due_before_its_interval(tmp_path) -> None:
    store = _store(tmp_path)
    store.record_attempt(_attempt("p1", "2026-07-01T00:00:00Z", "again"))
    early = datetime(2026, 7, 1, 12, tzinfo=UTC)  # only half a day later
    assert due_reviews(store.connection, now=early) == []


def test_most_overdue_first(tmp_path) -> None:
    store = _store(tmp_path)
    store.record_attempt(_attempt("recent", "2026-07-04T00:00:00Z", "again"))
    store.record_attempt(_attempt("old", "2026-06-01T00:00:00Z", "again"))
    due = due_reviews(store.connection, now=_NOW)
    assert [review.puzzle_id for review in due] == ["old", "recent"]


def test_locator_is_latest_non_empty(tmp_path) -> None:
    store = _store(tmp_path)
    # A pre-migration attempt (no locator) followed by a located one.
    store.record_attempt(
        _attempt("p1", "2026-06-01T00:00:00Z", "again", database_id="", database_path="")
    )
    store.record_attempt(
        _attempt("p1", "2026-07-01T00:00:00Z", "hard", database_path="/tmp/new.cpdb")
    )
    due = due_reviews(store.connection, now=_NOW)
    assert due[0].database_path == "/tmp/new.cpdb"


def test_legacy_attempts_still_schedule_without_a_locator(tmp_path) -> None:
    store = _store(tmp_path)
    store.record_attempt(
        _attempt("p1", "2026-07-01T00:00:00Z", "again", database_id="", database_path="")
    )
    due = due_reviews(store.connection, now=_NOW)
    assert due[0].puzzle_id == "p1"
    assert due[0].database_path == ""


def test_scoped_queue_keeps_only_that_decks_items(tmp_path) -> None:
    store = _store(tmp_path)
    store.record_attempt(_attempt("opening", "2026-07-01T00:00:00Z", "again", database_id="course"))
    store.record_attempt(_attempt("tactic", "2026-07-01T00:00:00Z", "again", database_id="tactics"))

    due = due_reviews(store.connection, now=_NOW, database_id="course")

    assert [review.puzzle_id for review in due] == ["opening"]


def test_scoped_queue_keeps_locatorless_items(tmp_path) -> None:
    # Attempts predating the locator migration ('' locator) resolve only
    # against the open deck, so a scoped queue must keep them.
    store = _store(tmp_path)
    store.record_attempt(
        _attempt("ancient", "2026-07-01T00:00:00Z", "again", database_id="", database_path="")
    )

    due = due_reviews(store.connection, now=_NOW, database_id="course")

    assert [review.puzzle_id for review in due] == ["ancient"]


def test_unscoped_queue_is_unchanged_by_scope_default(tmp_path) -> None:
    store = _store(tmp_path)
    store.record_attempt(_attempt("a", "2026-07-01T00:00:00Z", "again", database_id="one"))
    store.record_attempt(_attempt("b", "2026-07-01T00:00:00Z", "again", database_id="two"))

    assert len(due_reviews(store.connection, now=_NOW)) == 2
