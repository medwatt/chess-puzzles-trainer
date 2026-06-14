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
    if puzzle.pgn_text.strip():
        return puzzle.pgn_text

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
