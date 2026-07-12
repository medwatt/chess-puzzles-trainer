from __future__ import annotations

import sqlite3
from pathlib import Path

import chess
import pytest

from chess_puzzles.puzzle import Puzzle
from chess_puzzles.store.content import ContentDatabase, ContentMeta


FEN = "8/8/8/8/8/8/4K3/7k w - - 0 1"


def _meta() -> ContentMeta:
    return ContentMeta(database_id="db-1", name="Sample", created_at="t", updated_at="t")


def _sample_puzzles() -> list[Puzzle]:
    normal = Puzzle(
        title="Normal",
        initial_fen=FEN,
        moves=(chess.Move.from_uci("e2e3"), chess.Move.from_uci("h1g1")),
        comments=("intro", "after 1", "after 2"),
        theme="endgame",
        player_color=chess.WHITE,
        skip_first_move=False,
    )
    study = Puzzle(
        title="Study",
        initial_fen=FEN,
        moves=(),
        comments=("just text",),
    )
    lichess = Puzzle(
        title="Lichess",
        initial_fen=FEN,
        moves=(chess.Move.from_uci("e2e4"),),
        headers={"Rating": "1623"},
        theme="endgame",
        skip_first_move=True,
    )
    return [normal, study, lichess]


def _create(path: Path) -> ContentDatabase:
    return ContentDatabase.create(path, _meta(), _sample_puzzles())


def test_create_and_reopen_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "sample.cpdb"
    ids = [p.puzzle_id for p in _create(path).iter_puzzles()]
    db = ContentDatabase.open(path)
    assert db.count() == 3

    first = db.puzzle_at(0)
    assert first.ordinal == 1
    assert first.moves == (chess.Move.from_uci("e2e3"), chess.Move.from_uci("h1g1"))
    assert first.comments == ("intro", "after 1", "after 2")
    assert first.theme == "endgame"
    assert first.player_color == chess.WHITE
    assert first.skip_first_move is False

    # study page round-trips with no moves and a comment
    study = db.puzzle_at(1)
    assert study.moves == ()
    assert study.comments == ("just text",)

    # lichess puzzle keeps its headers + skip flag
    lichess = db.puzzle_at(2)
    assert lichess.skip_first_move is True
    assert lichess.headers.get("Rating") == "1623"

    assert db.index_of_id(first.puzzle_id) == 0
    assert db.puzzle_by_id(first.puzzle_id) == first
    assert db.puzzle_by_id("nope") is None
    assert db.index_of_id("nope") is None
    assert ids[0] == first.puzzle_id


def test_themes_and_theme_position(tmp_path: Path) -> None:
    db = _create(tmp_path / "sample.cpdb")
    assert db.themes() == ["endgame"]
    assert db.theme_position(0) == (1, 2)
    assert db.theme_position(1) is None  # study page has no theme
    assert db.theme_position(2) == (2, 2)


def test_difficulty_from_headers(tmp_path: Path) -> None:
    db = _create(tmp_path / "sample.cpdb")
    assert db.puzzle_at(2).headers.get("Rating") == "1623"
    assert db.puzzle_at(0).headers.get("Rating") is None


def test_set_skip_first_move_persists(tmp_path: Path) -> None:
    path = tmp_path / "sample.cpdb"
    _create(path).close()
    ContentDatabase.open(path).set_skip_first_move(1, True)
    assert ContentDatabase.open(path).puzzle_at(0).skip_first_move is True


def test_update_puzzles(tmp_path: Path) -> None:
    db = _create(tmp_path / "sample.cpdb")
    db.update_puzzles([(1, False, "newtheme")])
    assert db.puzzle_at(0).theme == "newtheme"


def test_delete_renumbers_ordinals(tmp_path: Path) -> None:
    db = _create(tmp_path / "sample.cpdb")
    db.delete_puzzles({2})
    assert db.count() == 2
    assert [db.puzzle_at(i).ordinal for i in range(2)] == [1, 2]


def test_study_pages_with_distinct_comments_get_distinct_ids(tmp_path: Path) -> None:
    # Move-free study pages share a position but carry different lesson text, so
    # each gets its own puzzle_id and is individually addressable cross-store.
    page_a = Puzzle(title="Page A", initial_fen=FEN, moves=(), comments=("aim of the course",))
    page_b = Puzzle(title="Page B", initial_fen=FEN, moves=(), comments=("how to use it",))
    db = ContentDatabase.create(tmp_path / "d.cpdb", _meta(), [page_a, page_b])
    assert db.count() == 2
    assert db.puzzle_at(0).puzzle_id != db.puzzle_at(1).puzzle_id
    assert db.index_of_id(db.puzzle_at(0).puzzle_id) == 0
    assert db.index_of_id(db.puzzle_at(1).puzzle_id) == 1


def test_move_free_pages_are_not_distinguished_by_title_only(tmp_path: Path) -> None:
    ex1 = Puzzle(title="Exercise 1", initial_fen=FEN, moves=(), comments=("same instructions",))
    ex2 = Puzzle(title="Exercise 2", initial_fen=FEN, moves=(), comments=("same instructions",))
    db = ContentDatabase.create(tmp_path / "d.cpdb", _meta(), [ex1, ex2])
    assert db.count() == 2
    assert db.puzzle_at(0).puzzle_id == db.puzzle_at(1).puzzle_id


def test_truly_identical_puzzles_are_still_kept(tmp_path: Path) -> None:
    # Byte-identical content collides on puzzle_id, but no puzzle is ever dropped.
    page = Puzzle(title="Dup", initial_fen=FEN, moves=(), comments=("same text",))
    db = ContentDatabase.create(tmp_path / "d.cpdb", _meta(), [page, page])
    assert db.count() == 2
    assert db.puzzle_at(0).puzzle_id == db.puzzle_at(1).puzzle_id


def test_create_replaces_existing_file(tmp_path: Path) -> None:
    # Re-creating at the same path (e.g. a PGN import saved over an existing
    # deck) replaces it instead of appending and colliding on primary keys.
    path = tmp_path / "deck.cpdb"
    ContentDatabase.create(path, _meta(), _sample_puzzles()).close()
    replacement = [Puzzle(title="Only", initial_fen=FEN, moves=(chess.Move.from_uci("e2e4"),))]
    db = ContentDatabase.create(path, _meta(), replacement)  # must not raise
    assert db.count() == 1
    assert db.puzzle_at(0).title == "Only"


def test_create_failure_keeps_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "deck.cpdb"
    ContentDatabase.create(path, _meta(), _sample_puzzles()).close()

    def broken_puzzles():
        yield Puzzle(title="Replacement", initial_fen=FEN, moves=(chess.Move.from_uci("e2e4"),))
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        ContentDatabase.create(path, _meta(), broken_puzzles())
    db = ContentDatabase.open(path)
    assert db.count() == 3
    assert db.puzzle_at(0).title == "Normal"
    assert not path.with_name(path.name + ".tmp").exists()


def test_in_memory_database(tmp_path: Path) -> None:
    meta = ContentMeta(database_id="favorites", name="All favorites")
    db = ContentDatabase.in_memory(meta, _sample_puzzles())
    assert db.count() == 3
    assert db.puzzle_at(0).ordinal == 1
    assert db.meta.name == "All favorites"


def test_open_rejects_wrong_version(tmp_path: Path) -> None:
    path = tmp_path / "old.cpdb"
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA user_version = 2")
    conn.close()
    with pytest.raises(ValueError):
        ContentDatabase.open(path)


def test_deck_kind_defaults_to_tactics() -> None:
    db = ContentDatabase.in_memory(_meta(), _sample_puzzles())

    assert db.kind == "tactics"
    assert db.meta_value("kind", "tactics") == "tactics"


def test_deck_kind_round_trips() -> None:
    db = ContentDatabase.in_memory(_meta(), _sample_puzzles())

    db.set_meta_value("kind", "repertoire")

    assert db.kind == "repertoire"


def test_set_meta_value_overwrites_existing_key() -> None:
    db = ContentDatabase.in_memory(_meta(), _sample_puzzles())

    db.set_meta_value("kind", "repertoire")
    db.set_meta_value("kind", "tactics")

    assert db.kind == "tactics"
    # Free-form meta keys never leak into the structured meta view.
    assert not hasattr(db.meta, "kind")
