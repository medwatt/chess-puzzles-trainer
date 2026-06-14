from __future__ import annotations

from importlib import resources


def _load_themes() -> tuple[str, ...]:
    text = resources.files(__package__).joinpath("themes.txt").read_text(encoding="utf-8")
    themes = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    return tuple(themes)


LICHESS_THEMES: tuple[str, ...] = _load_themes()
