"""Arena session decks: creation, refill sampling, and the frontier.

An arena is a normal content deck (kind='arena') that grows as puzzles are
served: the deck is the durable record of what was allocated to the session,
the attempt log decides everything else (frontier, rating, review). All the
inputs a refill needs are persisted in the deck's meta table so a session
can continue across restarts even if global settings changed.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from chess_puzzles.arena.rating import RATING_POLICY_ELO_V1, session_rating
from chess_puzzles.lichess.importer import LichessCsvImporter, LichessImportCriteria
from chess_puzzles.platform.paths import user_data_dir
from chess_puzzles.puzzle import Puzzle
from chess_puzzles.store import ContentDatabase, ContentMeta, DECK_KIND_ARENA, now_iso

# Small batches so difficulty adapts every few puzzles, not once per twenty.
DEFAULT_BATCH_SIZE = 5
# The sampling band around the current rating, biased slightly upward like
# lichess: training slightly above your level is the point of the mode.
BAND_BELOW = 100
BAND_ABOVE = 200
# Total rows one refill may scan across all widening retries. Sparse filters
# degrade to a short batch instead of an unbounded read on the UI thread.
ROW_BUDGET = 200_000
# Band multipliers tried in order until the batch is full; the last try is
# effectively unbounded because extreme ratings genuinely need a wide net.
_WIDENING = (1, 2, 4, 30)

META_START_RATING = "arena.start_rating"
META_THEMES = "arena.themes"
META_POPULARITY_MIN = "arena.popularity_min"
META_BATCH_SIZE = "arena.batch_size"
META_RATING_POLICY = "arena.rating_policy"
META_SELECTION_POLICY = "arena.selection_policy"

# How the next batch is chosen. Only one policy exists; the stamp records
# which one built each session so a future policy can leave old sessions
# sampling the way they always did.
SELECTION_POLICY_BAND_V1 = "band-v1"


@dataclass(frozen=True, slots=True)
class ArenaConfig:
    """Everything a refill needs; persisted in the arena deck's meta table."""

    csv_path: str
    start_rating: int
    popularity_min: int = 0
    themes: tuple[str, ...] = ()
    batch_size: int = DEFAULT_BATCH_SIZE


def write_arena_meta(database: ContentDatabase, config: ArenaConfig) -> None:
    database.set_meta_value(META_START_RATING, str(config.start_rating))
    database.set_meta_value(META_THEMES, json.dumps(list(config.themes)))
    database.set_meta_value(META_POPULARITY_MIN, str(config.popularity_min))
    database.set_meta_value(META_BATCH_SIZE, str(config.batch_size))
    database.set_meta_value(META_RATING_POLICY, RATING_POLICY_ELO_V1)
    database.set_meta_value(META_SELECTION_POLICY, SELECTION_POLICY_BAND_V1)


def selection_policy(database: ContentDatabase) -> str:
    """The validated sampling policy of this arena.

    A missing key (old file) or an unknown value (file from a newer app)
    deliberately falls back to band-v1 instead of guessing or failing --
    the queued content stays playable either way."""
    value = database.meta_value(META_SELECTION_POLICY, SELECTION_POLICY_BAND_V1)
    return value if value == SELECTION_POLICY_BAND_V1 else SELECTION_POLICY_BAND_V1


def read_arena_config(database: ContentDatabase) -> ArenaConfig:
    themes_raw = database.meta_value(META_THEMES, "[]")
    try:
        themes = tuple(str(theme) for theme in json.loads(themes_raw))
    except ValueError:
        themes = ()
    return ArenaConfig(
        csv_path=database.meta.source_path,
        start_rating=_int_meta(database, META_START_RATING, 1500),
        popularity_min=_int_meta(database, META_POPULARITY_MIN, 0),
        themes=themes,
        batch_size=_int_meta(database, META_BATCH_SIZE, DEFAULT_BATCH_SIZE),
    )


def _int_meta(database: ContentDatabase, key: str, default: int) -> int:
    try:
        return int(database.meta_value(key, str(default)))
    except ValueError:
        return default


def new_session_path(directory: Path, started: datetime) -> Path:
    """A fresh, collision-proof session filename.

    The timestamp is for humans; the uuid suffix guarantees two sessions
    started in the same second cannot resolve to (and overwrite) one file.
    """
    return directory / f"arena_{started:%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}.cpdb"


def create_arena(
    path: str | Path,
    config: ArenaConfig,
    name: str,
    puzzles: Iterable[Puzzle] = (),
) -> ContentDatabase:
    """Create a session file with its meta and first batch in one operation.

    Refuses to replace an existing file (ContentDatabase.create would); a
    failure while writing meta removes the just-created file so no partial
    session is ever published.
    """
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"session file already exists: {path}")
    meta = ContentMeta(
        database_id=str(uuid.uuid4()),
        name=name,
        description=f"Rated session starting at {config.start_rating}.",
        kind=DECK_KIND_ARENA,
        source_kind="lichess",
        source_path=config.csv_path,
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    database = ContentDatabase.create(path, meta, puzzles)
    try:
        write_arena_meta(database, config)
    except Exception:
        database.close()
        path.unlink(missing_ok=True)
        raise
    return database


def sample_batch(
    config: ArenaConfig,
    current_rating: float,
    exclude_ids: set[str],
    *,
    importer: LichessCsvImporter | None = None,
    row_budget: int = ROW_BUDGET,
) -> list[Puzzle]:
    """Sample the next batch around ``current_rating``, widening on shortfall.

    Returns fewer than batch_size (possibly zero) when the scan budget is
    exhausted -- the caller reports that instead of freezing the UI.
    """
    importer = importer or LichessCsvImporter()
    rating = round(current_rating)
    collected: list[Puzzle] = []
    excluded = set(exclude_ids)
    # Non-overlapping budget slices: their sum is exactly row_budget, so a
    # refill can never scan more rows than documented regardless of how many
    # widening attempts run. The widest attempt gets the remainder -- it is
    # the one that genuinely needs rows.
    slice_size = row_budget // len(_WIDENING)
    slices = [slice_size] * (len(_WIDENING) - 1)
    slices.append(row_budget - slice_size * (len(_WIDENING) - 1))
    for scale, slice_budget in zip(_WIDENING, slices):
        if len(collected) >= config.batch_size:
            break
        if slice_budget <= 0:
            continue
        criteria = LichessImportCriteria(
            sample_size=config.batch_size - len(collected),
            rating_min=max(0, rating - BAND_BELOW * scale),
            rating_max=min(3000, rating + BAND_ABOVE * scale),
            popularity_min=config.popularity_min,
            themes=config.themes,
        )
        batch = importer.sample_puzzles(
            config.csv_path, criteria, exclude_ids=excluded, row_budget=slice_budget
        )
        for puzzle in batch:
            if puzzle.puzzle_id not in excluded:
                collected.append(puzzle)
                excluded.add(puzzle.puzzle_id)
    return collected[: config.batch_size]


def refill(
    database: ContentDatabase,
    current_rating: float,
    *,
    importer: LichessCsvImporter | None = None,
    row_budget: int = ROW_BUDGET,
) -> int:
    """Append the next batch to the arena; returns how many were added."""
    config = read_arena_config(database)
    if not config.csv_path or not Path(config.csv_path).is_file():
        raise FileNotFoundError(config.csv_path or "no CSV configured for this arena")
    batch = sample_batch(
        config,
        current_rating,
        database.puzzle_ids(),
        importer=importer,
        row_budget=row_budget,
    )
    return database.append_puzzles(batch)


def arenas_dir() -> Path:
    """Where session files live -- deliberately outside the course folder."""
    return user_data_dir() / "arenas"


@dataclass(frozen=True, slots=True)
class ArenaSummary:
    """One session as the manager dialog lists it. Everything is derived on
    demand from the deck file and the attempt log; nothing here is cached."""

    path: Path
    database_id: str
    name: str
    created_at: str
    start_rating: int
    rating: int
    puzzle_count: int
    attempted: int
    themes: tuple[str, ...]


def list_sessions(conn: sqlite3.Connection, directory: Path | None = None) -> list[ArenaSummary]:
    """Every readable arena in the sessions folder, newest first.

    Files that are not arenas (or not readable) are skipped, not errors: the
    folder is app-managed, but nothing stops a user dropping files into it.
    """
    directory = directory if directory is not None else arenas_dir()
    if not directory.is_dir():
        return []
    summaries: list[ArenaSummary] = []
    for path in sorted(directory.glob("*.cpdb")):
        try:
            database = ContentDatabase.open(path)
        except (OSError, sqlite3.DatabaseError, ValueError):
            continue
        try:
            if database.kind != DECK_KIND_ARENA:
                continue
            config = read_arena_config(database)
            meta = database.meta
            attempted = conn.execute(
                "SELECT COUNT(DISTINCT puzzle_id) FROM attempt WHERE database_id = ?",
                (database.database_id,),
            ).fetchone()[0]
            summaries.append(
                ArenaSummary(
                    path=path,
                    database_id=database.database_id,
                    name=meta.name,
                    created_at=meta.created_at,
                    start_rating=config.start_rating,
                    rating=round(
                        session_rating(conn, database.database_id, config.start_rating)
                    ),
                    puzzle_count=database.count(),
                    attempted=attempted,
                    themes=config.themes,
                )
            )
        finally:
            database.close()
    summaries.sort(key=lambda summary: summary.created_at, reverse=True)
    return summaries


def frontier_index(database: ContentDatabase, attempted_ids: set[str]) -> int | None:
    """First ordinal (0-based) with no arena attempt, or None when all done.

    A refill queues several puzzles at once, so any of them -- not just the
    last -- may be unattempted; resume must find the first.
    """
    for index, puzzle in enumerate(database.iter_puzzles()):
        if puzzle.puzzle_id not in attempted_ids:
            return index
    return None


def puzzle_rating_of(puzzle: Puzzle) -> int | None:
    """The lichess difficulty stamped on attempts (None for unrated content)."""
    try:
        return int(puzzle.headers.get("Rating", "").strip())
    except (ValueError, AttributeError):
        return None
