"""The fixed Lichess vocabularies, shipped as newline lists beside this module.

Both are extracted from the puzzle database and refreshed with
``scripts/refresh_lichess_vocabulary.py``. They are read once at import and
exposed as tuples: the import dialog needs the whole vocabulary up front to
offer it, and the files are small enough that lazy loading would only add a
failure mode.

Opening tags are two-level. Each tagged puzzle stores *both* its family
(``Sicilian_Defense``) and its variation (``Sicilian_Defense_Najdorf_Variation``),
so matching is plain set intersection -- selecting a family catches every
variation under it without any prefix logic.
"""

from __future__ import annotations

from importlib import resources


def _load(filename: str) -> tuple[str, ...]:
    text = (
        resources.files("chess_puzzles.lichess")
        .joinpath(filename)
        .read_text(encoding="utf-8")
    )
    return tuple(
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


LICHESS_THEMES: tuple[str, ...] = _load("themes.txt")
LICHESS_OPENINGS: tuple[str, ...] = _load("openings.txt")
