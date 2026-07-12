"""Source-agnostic heuristics for importing an opening course from PGN.

Course exporters (Chessable, ChessReps, ChessMood, SCID studies, ...) all
produce plain PGN trees, but none of them declare which side the student is
training, and they scatter course/chapter/item names across different headers.
Rather than recognizing vendors, this module reads both answers out of the
game content itself:

- **Trained side**: repertoire authors end lines after *your* move, leaving
  you the good position, so the side that makes the final move of the
  drillable lines is the trained side. Validated across every course format
  we have seen; the import dialog still asks the user to confirm.
- **Naming**: whichever candidate header (Event/White/Black) repeats its
  value across games is chapter-like; whichever varies per game is
  title-like. Distinct-value counts decide, no vendor knowledge involved.

Everything here is a pure function over parsed games; the import dialog
presents the suggestions and the loader applies the user's final choices.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import chess
import chess.pgn

from chess_puzzles.puzzle.tree import MISTAKE_NAGS


# Headers that could plausibly carry chapter or item names.
NAMING_FIELDS = ("Event", "White", "Black")

# The sentinel offered alongside real headers: keep the loader's built-in
# title/theme behavior instead of reading a header.
DEFAULT_FIELD = ""


@dataclass(frozen=True, slots=True)
class ImportChoices:
    """The user's confirmed answers, consumed by the loader.

    ``trained_side`` fills in ``player_color`` for games whose headers do not
    declare one explicitly (explicit headers always win). ``chapter_field`` /
    ``title_field`` name the headers to read; DEFAULT_FIELD keeps the
    loader's built-in behavior.
    """

    trained_side: chess.Color | None = None
    chapter_field: str = DEFAULT_FIELD
    title_field: str = DEFAULT_FIELD


@dataclass(frozen=True, slots=True)
class FieldProfile:
    """How one candidate header behaves across the file's games."""

    name: str
    covered: int  # games where the header has a meaningful value
    distinct: int  # distinct meaningful values
    samples: tuple[str, ...]  # first few meaningful values, in file order


@dataclass(frozen=True, slots=True)
class CourseProfile:
    """Everything the import dialog needs to suggest and preview choices."""

    game_count: int
    white_finishers: int  # drillable lines whose final move is White's
    black_finishers: int
    fields: tuple[FieldProfile, ...]
    trained_side: chess.Color | None  # None when there is no evidence
    chapter_field: str  # suggested; DEFAULT_FIELD = no grouping header found
    title_field: str  # suggested; DEFAULT_FIELD = loader's built-in titles
    header_samples: tuple[dict[str, str], ...]  # first games' headers, for previews


def profile_pgn_file(path: str | Path) -> CourseProfile:
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        return profile_games(_read_games(handle.read()))


def profile_games(games: Sequence[chess.pgn.Game]) -> CourseProfile:
    white_finishers = 0
    black_finishers = 0
    for game in games:
        white_leaves, black_leaves = _count_line_finishers(game)
        white_finishers += white_leaves
        black_finishers += black_leaves

    fields = tuple(_profile_field(name, games) for name in NAMING_FIELDS)
    chapter_field, title_field = _suggest_naming(fields, len(games))
    return CourseProfile(
        game_count=len(games),
        white_finishers=white_finishers,
        black_finishers=black_finishers,
        fields=fields,
        trained_side=_suggest_side(white_finishers, black_finishers),
        chapter_field=chapter_field,
        title_field=title_field,
        header_samples=tuple(
            {key: str(value) for key, value in game.headers.items()} for game in games[:8]
        ),
    )


def _read_games(text: str) -> list[chess.pgn.Game]:
    stream = io.StringIO(text)
    games: list[chess.pgn.Game] = []
    while True:
        game = chess.pgn.read_game(stream)
        if game is None:
            return games
        games.append(game)


def _count_line_finishers(game: chess.pgn.Game) -> tuple[int, int]:
    """Leaves of the drillable tree, counted by which color moved last.

    Mirrors the loader's line enumeration: mistake-marked variations are
    refutation content, and null moves end a line, so neither counts as a
    finisher. Parity from the root position identifies the mover without
    replaying moves.
    """
    try:
        root_turn = game.board().turn
    except ValueError:
        return 0, 0
    white = black = 0
    stack: list[tuple[chess.pgn.GameNode, int]] = [(game, 0)]
    while stack:
        node, depth = stack.pop()
        children = [
            child
            for child in node.variations
            if child.move and child.move != chess.Move.null() and not (MISTAKE_NAGS & child.nags)
        ]
        if not children:
            if depth > 0:
                # After ``depth`` plies the side to move alternates from the
                # root; the final mover is the other color.
                final_mover = root_turn if depth % 2 == 1 else not root_turn
                if final_mover == chess.WHITE:
                    white += 1
                else:
                    black += 1
            continue
        stack.extend((child, depth + 1) for child in children)
    return white, black


def _suggest_side(white_finishers: int, black_finishers: int) -> chess.Color | None:
    if white_finishers == black_finishers:
        return None
    return chess.WHITE if white_finishers > black_finishers else chess.BLACK


def _meaningful(value: str) -> str:
    value = value.strip()
    return "" if value in ("", "?") else value


def _profile_field(name: str, games: Sequence[chess.pgn.Game]) -> FieldProfile:
    values = [_meaningful(game.headers.get(name, "")) for game in games]
    present = [value for value in values if value]
    seen: dict[str, None] = dict.fromkeys(present)  # ordered distinct
    return FieldProfile(
        name=name,
        covered=len(present),
        distinct=len(seen),
        samples=tuple(list(seen)[:5]),
    )


def _suggest_naming(fields: tuple[FieldProfile, ...], game_count: int) -> tuple[str, str]:
    """Pick (chapter_field, title_field) from distinct-value counts.

    A chapter header groups several games under one value, so it should have
    at least two distinct values (otherwise the whole file is one chapter)
    and average at least two games per value. A title header is the most
    varied one. When no field qualifies as a grouper, the least varied field
    still names the single chapter; when nothing distinguishes titles, the
    loader's built-in titles are kept.
    """
    candidates = [
        field for field in fields if field.covered * 2 >= game_count and field.distinct > 0
    ]
    if not candidates:
        return DEFAULT_FIELD, DEFAULT_FIELD

    groupers = [field for field in candidates if 2 <= field.distinct <= max(2, game_count // 2)]
    chapter = (
        min(groupers, key=lambda field: field.distinct)
        if groupers
        else min(candidates, key=lambda field: field.distinct)
    )

    title = max(candidates, key=lambda field: field.distinct)
    if title.name == chapter.name or title.distinct <= chapter.distinct:
        return chapter.name, DEFAULT_FIELD
    return chapter.name, title.name
