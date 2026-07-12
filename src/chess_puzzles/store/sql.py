from __future__ import annotations


CONTENT_SCHEMA_SQL = """
PRAGMA user_version = 1;

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS puzzle (
    ordinal         INTEGER PRIMARY KEY,         -- 1-based display order; the stable row identity
    puzzle_id       TEXT NOT NULL,               -- content fingerprint; cross-store key, NOT unique
    title           TEXT NOT NULL,
    initial_fen     TEXT NOT NULL,
    moves           TEXT NOT NULL,
    comments        TEXT NOT NULL,
    headers         TEXT NOT NULL,
    pgn_text        TEXT NOT NULL,
    player_color    TEXT,
    skip_first_move INTEGER NOT NULL DEFAULT 0,
    theme           TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_puzzle_id ON puzzle(puzzle_id);
CREATE INDEX IF NOT EXISTS idx_puzzle_theme ON puzzle(theme);
"""


USER_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS attempt (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    puzzle_id   TEXT NOT NULL,
    at          TEXT NOT NULL,
    outcome     TEXT NOT NULL,
    mistakes    INTEGER NOT NULL DEFAULT 0,
    aids        INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER,
    grade       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempt_puzzle ON attempt(puzzle_id);
CREATE INDEX IF NOT EXISTS idx_attempt_at ON attempt(at);

CREATE TABLE IF NOT EXISTS note (
    puzzle_id  TEXT PRIMARY KEY,
    text       TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS favorite (
    puzzle_id     TEXT NOT NULL,
    database_id   TEXT NOT NULL,
    database_path TEXT NOT NULL,
    added_at      TEXT NOT NULL,
    PRIMARY KEY (puzzle_id, database_id)
);
CREATE INDEX IF NOT EXISTS idx_favorite_database ON favorite(database_id);

CREATE TABLE IF NOT EXISTS ui_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


# Migration appended after VISION_SCHEMA_SQL (see _USER_MIGRATIONS): adds the
# deck locator to attempts so the review queue can find a due puzzle's content
# without that deck being open (the same locator the favorite table carries).
# Attempts recorded before this migration keep '' and resolve against the
# currently open deck until the puzzle is attempted once more.
ATTEMPT_LOCATOR_SQL = """
ALTER TABLE attempt ADD COLUMN database_id TEXT NOT NULL DEFAULT '';
ALTER TABLE attempt ADD COLUMN database_path TEXT NOT NULL DEFAULT '';
"""


# Migration appended after USER_SCHEMA_SQL (see _USER_MIGRATIONS): adds the
# board-vision drill history. tp/fp/fn store the per-square true-positive /
# false-positive / false-negative counts so richer scoring (precision/recall)
# and future spaced repetition need no schema change.
VISION_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS vision_attempt (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    drill_id    TEXT NOT NULL,
    at          TEXT NOT NULL,
    fen         TEXT NOT NULL,
    orientation INTEGER NOT NULL,           -- 1 = white at bottom, 0 = black
    answer      TEXT NOT NULL,              -- comma-separated square indices
    clicks      TEXT NOT NULL,              -- comma-separated square indices
    tp          INTEGER NOT NULL,
    fp          INTEGER NOT NULL,
    fn          INTEGER NOT NULL,
    passed      INTEGER NOT NULL,           -- 1 = exact match
    elapsed_ms  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_vision_drill ON vision_attempt(drill_id);
CREATE INDEX IF NOT EXISTS idx_vision_at ON vision_attempt(at);
"""


LIBRARY_SCHEMA_SQL = """
CREATE TABLE library_root (
    path      TEXT PRIMARY KEY,
    recursive INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE library_course (
    database_id   TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    kind          TEXT NOT NULL DEFAULT 'tactics',
    puzzle_count  INTEGER NOT NULL DEFAULT 0,
    chapter_count INTEGER NOT NULL DEFAULT 0,
    pinned        INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'active',
    added_at      TEXT NOT NULL,
    indexed_at    TEXT NOT NULL
);

CREATE TABLE library_location (
    path        TEXT PRIMARY KEY,
    database_id TEXT NOT NULL REFERENCES library_course(database_id) ON DELETE CASCADE,
    mtime_ns    INTEGER NOT NULL,
    file_size   INTEGER NOT NULL,
    available   INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_library_location_database ON library_location(database_id);

CREATE TABLE library_tag (
    tag_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL COLLATE NOCASE UNIQUE
);

CREATE TABLE library_course_tag (
    database_id TEXT NOT NULL REFERENCES library_course(database_id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES library_tag(tag_id) ON DELETE CASCADE,
    PRIMARY KEY (database_id, tag_id)
);
"""
