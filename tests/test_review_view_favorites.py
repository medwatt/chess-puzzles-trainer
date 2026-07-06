from pathlib import Path
from types import SimpleNamespace

from chess_puzzles.app.main_window import MainWindow
from chess_puzzles.store import FavoriteRef, UserStore


def _window(tmp_path: Path, *, review_view: bool) -> tuple[MainWindow, list[str]]:
    icons: list[str] = []
    window = MainWindow.__new__(MainWindow)
    window.user_store = UserStore.open(tmp_path / "u.db")
    window.session = SimpleNamespace(puzzle=SimpleNamespace(puzzle_id="p1"))
    window.database = SimpleNamespace(database_id="favorites")  # the in-memory list view
    window.database_path = None
    window.favorites_view = True
    window.review_view = review_view
    window.favorite_sources = [FavoriteRef("p1", "deck1", "/tmp/deck1.cpdb")]
    window.current_index = 0
    window._status_var = SimpleNamespace(set=lambda _value: None)
    window._layout = SimpleNamespace(
        favorite_button=None,
        set_toolbar_button_icon=lambda _button, icon, _label: icons.append(icon),
    )
    return window, icons


def test_review_view_favorite_button_toggles_the_source_deck(tmp_path: Path) -> None:
    window, icons = _window(tmp_path, review_view=True)

    window.toggle_current_favorite()
    assert window.user_store.is_favorite("p1", "deck1")
    assert window.user_store.favorite_refs()[0].database_path == "/tmp/deck1.cpdb"
    # The puzzle stays in the review list; only the star state changes.
    assert window.favorite_sources and icons[-1] == "favorite_on.png"

    window.toggle_current_favorite()
    assert not window.user_store.is_favorite("p1", "deck1")
    assert icons[-1] == "favorite_off.png"


def test_favorites_view_button_still_removes_from_the_list(tmp_path: Path) -> None:
    window, _icons = _window(tmp_path, review_view=False)
    window.user_store.add_favorite("p1", "deck1", "/tmp/deck1.cpdb")
    removed = []
    window._remove_current_favorite_source = lambda: removed.append(True)

    window.toggle_current_favorite()
    assert removed  # unchanged favorites-view behaviour
