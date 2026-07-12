from pathlib import Path
from types import SimpleNamespace

from chess_puzzles.app.main_database_actions import MainDatabaseActions
from chess_puzzles.store import UserStore


class _Status:
    def __init__(self) -> None:
        self.value = ""

    def set(self, value: str) -> None:
        self.value = value


def _window(tmp_path: Path, recent: tuple[str, ...], current: Path | None = None):
    return SimpleNamespace(
        user_store=UserStore.open(tmp_path / "user.db"),
        state=SimpleNamespace(settings=SimpleNamespace(recent_database_paths=recent)),
        database_path=current,
        _status_var=_Status(),
    )


def test_open_most_recent_skips_missing_entries(tmp_path: Path) -> None:
    available = tmp_path / "available.cpdb"
    available.touch()
    window = _window(tmp_path, (str(tmp_path / "missing.cpdb"), str(available)))
    actions = MainDatabaseActions(window)
    opened: list[Path] = []
    actions.open_database = opened.append

    actions.open_most_recent_course()

    assert opened == [available]


def test_open_most_recent_does_not_reload_current_course(tmp_path: Path) -> None:
    current = tmp_path / "current.cpdb"
    current.touch()
    window = _window(tmp_path, (str(current),), current)
    actions = MainDatabaseActions(window)
    opened: list[Path] = []
    actions.open_database = opened.append

    actions.open_most_recent_course()

    assert opened == []
    assert window._status_var.value == "The most recent course is already open."
