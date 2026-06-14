from __future__ import annotations

import io
from pathlib import Path
from typing import TextIO

import chess
import chess.pgn

from chess_puzzles.puzzle import Puzzle
from chess_puzzles.puzzle.skip import infer_skip_first_move


class PgnLoader:
    """Adapter around python-chess PGN parsing."""

    def load_file(self, path: str | Path) -> list[Puzzle]:
        with Path(path).open("r", encoding="utf-8-sig") as handle:
            return self.load(handle)

    def load(self, handle: TextIO) -> list[Puzzle]:
        # Normalise known exporter quirks, then parse each game into a puzzle,
        # keeping only games that are actually training items.
        stream = io.StringIO(self._collapse_movetext_blank_lines(handle.read()))

        puzzles: list[Puzzle] = []
        source_index = 0
        while True:
            game = chess.pgn.read_game(stream)
            if game is None:
                break
            source_index += 1
            puzzle = self._build_puzzle(game, source_index)
            if self._has_content(puzzle):
                puzzles.append(puzzle)
        return puzzles

    def _build_puzzle(self, game: chess.pgn.Game, source_index: int) -> Puzzle:
        headers = {key: str(value) for key, value in game.headers.items()}
        moves, comments = self._mainline(game)
        initial_fen = game.board().fen()
        player_color = self._player_color(headers)
        return Puzzle(
            title=self._title(headers, source_index),
            initial_fen=initial_fen,
            moves=moves,
            comments=comments,
            headers=headers,
            pgn_text=self._full_pgn_text(game),
            ordinal=source_index,
            player_color=player_color,
            skip_first_move=infer_skip_first_move(initial_fen, moves, player_color),
        )

    @staticmethod
    def _has_content(puzzle: Puzzle) -> bool:
        """Whether a parsed game is a training item.

        A puzzle needs something to solve or to read. A game with no moves and
        no comments -- a header-only stub or an unrecoverable fragment -- is
        not one, so it is dropped rather than shown as a blank position.
        """
        return bool(puzzle.moves) or any(comment.strip() for comment in puzzle.comments)

    @staticmethod
    def _collapse_movetext_blank_lines(text: str) -> str:
        """Remove blank lines that sit inside a game's movetext.

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
            in_comment = PgnLoader._scan_comment_state(line, in_comment)
        return "\n".join(kept) + "\n"

    @staticmethod
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

    def _mainline(self, game: chess.pgn.Game) -> tuple[tuple[chess.Move, ...], tuple[str, ...]]:
        """Collect the mainline solution moves and their comments.

        ``comments[0]`` is the text before the first move; ``comments[i]`` is the
        text after move ``i`` (see ``pgn.utils``).

        A ``--`` null move (UCI ``0000``) is a pass that some courses use to hang
        lesson text off a static position; it is not a solution move. The move
        list stops at the first null move, and that node's commentary is folded
        into the preceding comment so the study text is not lost.
        """
        moves: list[chess.Move] = []
        comments = [game.comment.strip()]
        node: chess.pgn.GameNode = game
        while node.variations:
            node = node.variation(0)
            if not node.move:  # null / pass move -> not part of the solution
                self._fold_comment(comments, node.comment.strip())
                break
            moves.append(node.move)
            comments.append(node.comment.strip())
        return tuple(moves), tuple(comments)

    @staticmethod
    def _fold_comment(comments: list[str], text: str) -> None:
        if not text:
            return
        comments[-1] = f"{comments[-1]}\n\n{text}".strip() if comments[-1] else text

    def _full_pgn_text(self, game: chess.pgn.Game) -> str:
        exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
        return game.accept(exporter)

    def _title(self, headers: dict[str, str], source_index: int) -> str:
        event = headers.get("Event", "").strip()
        white = headers.get("White", "").strip()
        black = headers.get("Black", "").strip()

        if white and black and white != "?" and black != "?":
            players = f"{white}: {black}"
            return f"{event} - {players}" if event and event != "?" else players

        return event if event and event != "?" else f"Puzzle {source_index}"

    def _player_color(self, headers: dict[str, str]) -> chess.Color | None:
        for key in ("PuzzleSide", "TrainingSide", "UserColor", "PlayerColor", "Orientation"):
            value = headers.get(key, "").strip().lower()
            if value in ("white", "w"):
                return chess.WHITE
            if value in ("black", "b"):
                return chess.BLACK
        return None
