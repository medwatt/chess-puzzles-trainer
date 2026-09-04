from __future__ import annotations

import chess
import chess.pgn

from chess_puzzles.puzzle import Puzzle


PGN_HEADER_ORDER = (
    "Event",
    "Site",
    "Date",
    "Round",
    "White",
    "Black",
    "Result",
    "SetUp",
    "FEN",
    "Annotator",
    "Source",
)


def ordered_header_keys(headers: dict[str, str]) -> list[str]:
    ordered = [key for key in PGN_HEADER_ORDER if key in headers]
    ordered.extend(key for key in headers if key not in PGN_HEADER_ORDER)
    return ordered


def pgn_for_puzzle(puzzle: Puzzle) -> str:
    if puzzle.canonical_pgn.strip():
        return puzzle.canonical_pgn

    game = chess.pgn.Game()
    for key in ordered_header_keys(puzzle.headers):
        game.headers[key] = puzzle.headers[key]

    if puzzle.initial_fen != chess.STARTING_FEN:
        game.headers["SetUp"] = "1"
        game.headers["FEN"] = puzzle.initial_fen

    # Comment convention (see PgnLoader._mainline): comments[0]
    # precedes the first move and comments[i + 1] follows move i.
    if puzzle.comments and puzzle.comments[0]:
        game.comment = puzzle.comments[0]

    node = game
    for index, move in enumerate(puzzle.moves):
        node = node.add_variation(move)
        comment_index = index + 1
        if comment_index < len(puzzle.comments) and puzzle.comments[comment_index]:
            node.comment = puzzle.comments[comment_index]

    exporter = chess.pgn.StringExporter(headers=True, variations=False, comments=True)
    return game.accept(exporter)


def normalize_pgn_text(text: str) -> str:
    """Remove blank lines that sit inside a game's movetext.

    Every path that parses a PGN file must apply this first, or the paths
    disagree: profiling a course counted games the loader would go on to
    merge, so the import dialog could describe a different file than the
    one that was actually imported.

    Some exporters (e.g. Chessable) put a blank line between a leading
    comment and the first move. The PGN spec treats a blank line as the
    end of the movetext, so python-chess splits such a game in two: a
    move-less game, plus a headerless game whose moves are then parsed
    against the default starting position and silently discarded -- the
    solution is lost.

    A blank line is a genuine game separator only when the next non-blank
    line starts a new header (``[``). Any other blank line is stray and is
    dropped, unless it falls inside a ``{...}`` comment (where blank lines
    are legitimate text and do not terminate the movetext).
    """
    lines = text.splitlines()
    kept: list[str] = []
    in_comment = False
    for index, line in enumerate(lines):
        if not in_comment and line.strip() == "":
            following = next(
                (lines[j] for j in range(index + 1, len(lines)) if lines[j].strip()),
                "",
            )
            if not following.lstrip().startswith("["):
                continue
        kept.append(line)
        in_comment = _scan_comment_state(line, in_comment)
    return "\n".join(kept) + "\n"

def _scan_comment_state(line: str, in_comment: bool) -> bool:
    """Return whether we are inside a ``{...}`` comment after consuming ``line``.

    Mirrors python-chess exactly so our notion of "inside a comment" matches
    the parser's: a ``{`` opens a comment that ends at the very next ``}``
    (PGN comments do not nest, so a ``{`` within one is literal text), ``;``
    starts a rest-of-line comment when not already inside braces, and header
    lines never open a comment. Tracking nesting with a counter instead would
    desync permanently on the unbalanced/nested braces real exports contain.
    """
    if not in_comment and line.lstrip().startswith("["):
        return False
    for char in line:
        if in_comment:
            if char == "}":
                in_comment = False
        elif char == "{":
            in_comment = True
        elif char == ";":
            break
    return in_comment
