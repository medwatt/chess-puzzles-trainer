from __future__ import annotations

from pathlib import Path

from chess_puzzles.arena.service import (
    ArenaConfig,
    create_arena,
    frontier_index,
    puzzle_rating_of,
    read_arena_config,
    refill,
    sample_batch,
)
from chess_puzzles.arena.rating import RATING_POLICY_ELO_V1
from chess_puzzles.store import DECK_KIND_ARENA


_FEN = "8/8/8/8/8/8/4K3/7k w - - 0 1"


def _write_csv(path: Path, rows: list[tuple[str, int]]) -> None:
    lines = ["PuzzleId,FEN,Moves,Rating,Popularity,Themes,GameUrl"]
    lines.extend(f"{pid},{_FEN},e2e3,{rating},95,endgame mate," for pid, rating in rows)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _config(csv_path: Path, start_rating: int = 1500, batch_size: int = 3) -> ArenaConfig:
    return ArenaConfig(csv_path=str(csv_path), start_rating=start_rating, batch_size=batch_size)


def test_arena_meta_round_trip(tmp_path: Path) -> None:
    from chess_puzzles.arena.service import SELECTION_POLICY_BAND_V1, selection_policy

    csv = tmp_path / "lichess.csv"
    _write_csv(csv, [("a", 1500)])
    config = ArenaConfig(
        csv_path=str(csv), start_rating=1730, popularity_min=40,
        themes=("fork", "endgame"), batch_size=7,
    )
    database = create_arena(tmp_path / "arena.cpdb", config, "Arena test")
    assert database.kind == DECK_KIND_ARENA
    assert database.meta_value("arena.rating_policy") == RATING_POLICY_ELO_V1
    assert database.meta_value("arena.selection_policy") == SELECTION_POLICY_BAND_V1
    assert read_arena_config(database) == config
    database.close()
    # Retained across reopen; validated fallback for missing/unknown values.
    from chess_puzzles.store import ContentDatabase

    database = ContentDatabase.open(tmp_path / "arena.cpdb")
    assert selection_policy(database) == SELECTION_POLICY_BAND_V1
    database.set_meta_value("arena.selection_policy", "band-v99")
    assert selection_policy(database) == SELECTION_POLICY_BAND_V1  # deliberate fallback
    database.set_meta_value("arena.selection_policy", "")
    assert selection_policy(database) == SELECTION_POLICY_BAND_V1  # missing -> v1
    database.close()


def test_sample_batch_bands_around_rating_and_dedupes(tmp_path: Path) -> None:
    csv = tmp_path / "lichess.csv"
    _write_csv(csv, [("low", 900), ("in1", 1450), ("in2", 1600), ("high", 2600)])
    batch = sample_batch(_config(csv), 1500, exclude_ids={"in2"})
    ids = {puzzle.puzzle_id for puzzle in batch}
    # in1 matches the base band; in2 is excluded; low/high only match after
    # widening, which runs because the batch is still short.
    assert "in1" in ids
    assert "in2" not in ids
    assert len(ids) == len(batch)  # no duplicates within a batch


def test_sample_batch_widens_band_on_shortfall(tmp_path: Path) -> None:
    csv = tmp_path / "lichess.csv"
    _write_csv(csv, [("far", 2600)])
    batch = sample_batch(_config(csv, start_rating=1200, batch_size=1), 1200, set())
    assert [puzzle.puzzle_id for puzzle in batch] == ["far"]


def test_sample_batch_respects_row_budget(tmp_path: Path) -> None:
    csv = tmp_path / "lichess.csv"
    _write_csv(csv, [(f"p{i}", 1500) for i in range(50)])
    batch = sample_batch(_config(csv, batch_size=50), 1500, set(), row_budget=0)
    assert batch == []


def test_sample_batch_budget_is_cumulative_across_widening(tmp_path: Path) -> None:
    # An impossible filter forces every widening attempt to run; the budgets
    # handed to the importer must sum to at most the total, for any total.
    class CountingImporter:
        def __init__(self) -> None:
            self.budgets: list[int] = []

        def sample_puzzles(self, _csv, _criteria, *, exclude_ids, row_budget):
            self.budgets.append(row_budget)
            return []

    for total in (0, 1, 3, 10, 200_000):
        importer = CountingImporter()
        batch = sample_batch(
            _config(tmp_path / "unused.csv"), 1500, set(),
            importer=importer, row_budget=total,
        )
        assert batch == []
        assert sum(importer.budgets) <= total
        assert all(budget > 0 for budget in importer.budgets)
        if total > 0:
            assert sum(importer.budgets) == total  # nothing silently wasted


def test_refill_appends_after_existing_ordinals(tmp_path: Path) -> None:
    csv = tmp_path / "lichess.csv"
    _write_csv(csv, [("a", 1500), ("b", 1520), ("c", 1480), ("d", 1510)])
    database = create_arena(tmp_path / "arena.cpdb", _config(csv, batch_size=2), "Arena")
    first = refill(database, 1500)
    second = refill(database, 1500)
    assert first == 2
    assert second == 2  # dedupe against the deck leaves only the other two
    ids = [puzzle.puzzle_id for puzzle in database.iter_puzzles()]
    assert len(ids) == 4
    assert len(set(ids)) == 4
    ordinals = [puzzle.ordinal for puzzle in database.iter_puzzles()]
    assert ordinals == [1, 2, 3, 4]
    # The pool is exhausted now: a further refill finds nothing new.
    assert refill(database, 1500) == 0
    database.close()


def test_new_session_paths_never_collide(tmp_path: Path) -> None:
    from datetime import datetime
    from chess_puzzles.arena.service import new_session_path

    started = datetime(2026, 7, 16, 12, 0, 0)
    first = new_session_path(tmp_path, started)
    second = new_session_path(tmp_path, started)  # same wall-clock second
    assert first != second


def test_create_arena_refuses_existing_file(tmp_path: Path) -> None:
    csv = tmp_path / "lichess.csv"
    _write_csv(csv, [("a", 1500)])
    path = tmp_path / "arena.cpdb"
    create_arena(path, _config(csv), "First").close()
    before = path.read_bytes()
    try:
        create_arena(path, _config(csv), "Second")
    except FileExistsError:
        pass
    else:
        raise AssertionError("expected FileExistsError")
    assert path.read_bytes() == before  # the first session is untouched


def test_failed_initial_batch_publishes_no_partial_file(tmp_path: Path) -> None:
    import chess
    from chess_puzzles.puzzle import Puzzle

    csv = tmp_path / "lichess.csv"
    _write_csv(csv, [("a", 1500)])
    path = tmp_path / "arena.cpdb"

    def exploding_batch():
        yield Puzzle(title="a", initial_fen=_FEN, moves=(chess.Move.from_uci("e2e3"),), puzzle_id="a")
        raise RuntimeError("boom")

    try:
        create_arena(path, _config(csv), "Arena", exploding_batch())
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError")
    assert not path.exists()


def test_refill_without_csv_raises(tmp_path: Path) -> None:
    csv = tmp_path / "lichess.csv"
    _write_csv(csv, [("a", 1500)])
    database = create_arena(tmp_path / "arena.cpdb", _config(csv), "Arena")
    csv.unlink()
    try:
        refill(database, 1500)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("expected FileNotFoundError")
    # The already-queued content still reads fine.
    assert database.count() == 0 or all(p.puzzle_id for p in database.iter_puzzles())
    database.close()


def test_frontier_is_first_unattempted_ordinal(tmp_path: Path) -> None:
    # Deterministic deck order (refill samples from a random CSV offset).
    import chess
    from chess_puzzles.puzzle import Puzzle

    csv = tmp_path / "lichess.csv"
    _write_csv(csv, [("a", 1500)])
    database = create_arena(tmp_path / "arena.cpdb", _config(csv), "Arena")
    database.append_puzzles(
        Puzzle(title=pid, initial_fen=_FEN, moves=(chess.Move.from_uci("e2e3"),), puzzle_id=pid)
        for pid in ("a", "b", "c")
    )
    assert frontier_index(database, set()) == 0
    assert frontier_index(database, {"a"}) == 1
    # Skipping ahead does not hide an earlier gap.
    assert frontier_index(database, {"a", "c"}) == 1
    assert frontier_index(database, {"a", "b", "c"}) is None
    database.close()


def test_list_sessions_derives_rating_and_skips_non_arenas(tmp_path: Path) -> None:
    from chess_puzzles.arena.service import list_sessions
    from chess_puzzles.store import Attempt, UserStore

    csv = tmp_path / "lichess.csv"
    _write_csv(csv, [("a", 1500), ("b", 1500), ("c", 1500)])
    sessions_dir = tmp_path / "arenas"
    sessions_dir.mkdir()

    arena = create_arena(sessions_dir / "arena_one.cpdb", _config(csv, start_rating=1500), "One")
    refill(arena, 1500)
    arena_id = arena.database_id
    arena.close()
    # A stray ordinary course and a garbage file in the folder are ignored.
    from chess_puzzles.store import ContentDatabase, ContentMeta, now_iso

    ContentDatabase.create(
        sessions_dir / "not_arena.cpdb",
        ContentMeta(database_id="plain", name="Plain", created_at=now_iso(), updated_at=now_iso()),
        (),
    ).close()
    (sessions_dir / "junk.cpdb").write_text("not a database", encoding="utf-8")

    store = UserStore.open(tmp_path / "userdata.db")
    store.record_attempt(
        Attempt(
            puzzle_id="a", at="2026-07-16T00:00:00Z", outcome="gave_up", mistakes=0,
            aids=0, grade="again", database_id=arena_id, puzzle_rating=1500,
        )
    )

    sessions = list_sessions(store.connection, sessions_dir)
    assert [s.name for s in sessions] == ["One"]
    assert sessions[0].puzzle_count == 3
    assert sessions[0].attempted == 1
    assert sessions[0].rating == 1500 - 20
    assert sessions[0].start_rating == 1500


def test_library_scan_purges_arena_rows_registered_by_older_versions(tmp_path: Path) -> None:
    from chess_puzzles.store import UserStore

    csv = tmp_path / "lichess.csv"
    _write_csv(csv, [("a", 1500)])
    arena_path = tmp_path / "arena.cpdb"
    arena = create_arena(arena_path, _config(csv), "Arena")
    store = UserStore.open(tmp_path / "userdata.db")
    library = store.library
    library.register(arena_path, arena)  # what pre-exclusion versions did
    arena.close()

    library.scan()

    assert not any(course.kind == DECK_KIND_ARENA for course in library.courses())


def test_library_forget_removes_course_and_locations(tmp_path: Path) -> None:
    from chess_puzzles.store import UserStore

    csv = tmp_path / "lichess.csv"
    _write_csv(csv, [("a", 1500)])
    arena_path = tmp_path / "arena.cpdb"
    arena = create_arena(arena_path, _config(csv), "Arena")
    store = UserStore.open(tmp_path / "userdata.db")
    library = store.library
    library.register(arena_path, arena)
    assert any(course.database_id == arena.database_id for course in library.courses())

    library.forget(arena.database_id)

    assert not any(course.database_id == arena.database_id for course in library.courses())
    arena.close()


def test_puzzle_rating_of_reads_the_header(tmp_path: Path) -> None:
    csv = tmp_path / "lichess.csv"
    _write_csv(csv, [("a", 1234)])
    batch = sample_batch(_config(csv, batch_size=1), 1234, set())
    assert puzzle_rating_of(batch[0]) == 1234
