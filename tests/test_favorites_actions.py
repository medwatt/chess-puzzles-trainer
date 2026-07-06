from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import chess

from chess_puzzles.app.main_database_actions import MainDatabaseActions
from chess_puzzles.app.main_window import MainWindow
from chess_puzzles.puzzle import Puzzle
from chess_puzzles.store import ContentDatabase, ContentMeta, FavoriteRef, UserStore


FEN = "8/8/8/8/8/8/4K3/7k w - - 0 1"


class _Status:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


def test_export_favorites_this_deck_uses_live_content(tmp_path: Path, monkeypatch) -> None:
    puzzle = Puzzle(
        title="Favorite",
        initial_fen=FEN,
        moves=(chess.Move.from_uci("e2e3"),),
        comments=("intro", "done"),
    )
    db_path = tmp_path / "deck.cpdb"
    db = ContentDatabase.create(db_path, ContentMeta(database_id="db1", name="Deck"), [puzzle])
    user_store = UserStore.open(tmp_path / "userdata.db")
    favorite = db.puzzle_at(0)
    user_store.add_favorite(favorite.puzzle_id, db.database_id, str(db_path))

    out_path = tmp_path / "favorites.pgn"
    monkeypatch.setattr(
        "chess_puzzles.app.main_database_actions.filedialog.asksaveasfilename",
        lambda **_kwargs: str(out_path),
    )

    status = _Status()
    window = SimpleNamespace(
        root=None,
        database=db,
        database_path=db_path,
        favorites_view=False,
        user_store=user_store,
        _status_var=status,
    )

    MainDatabaseActions(window).export_favorites(scope="deck")

    assert status.value == "Exported 1 favorite(s)."
    text = out_path.read_text(encoding="utf-8")
    assert "Ke3" in text
    assert "intro" in text


def test_unfavorite_from_favorites_view_removes_visible_source(tmp_path: Path) -> None:
    user_store = UserStore.open(tmp_path / "userdata.db")
    user_store.add_favorite("p1", "db1", str(tmp_path / "deck.cpdb"))
    source = FavoriteRef("p1", "db1", str(tmp_path / "deck.cpdb"))
    db = ContentDatabase.in_memory(
        ContentMeta(database_id="favorites", name="Favorites"),
        [Puzzle(title="Favorite", initial_fen=FEN, moves=(chess.Move.from_uci("e2e3"),), puzzle_id="p1")],
    )

    status = _Status()
    window = MainWindow.__new__(MainWindow)
    window.session = SimpleNamespace(puzzle=SimpleNamespace(puzzle_id="p1"))
    window.favorites_view = True
    window.review_view = False
    window.current_index = 0
    window.favorite_sources = [source]
    window.user_store = user_store
    window.database = db
    window._status_var = status
    window._database = SimpleNamespace(show_empty_state=lambda message: status.set(message))

    window.toggle_current_favorite()

    assert user_store.favorite_ids("db1") == set()
    assert window.favorite_sources == []
    assert status.value == "Removed from favorites."
