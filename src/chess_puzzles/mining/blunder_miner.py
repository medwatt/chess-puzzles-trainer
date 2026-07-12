"""Mine "avoid the blunder" puzzles from the Lichess puzzle CSV.

Every row of that CSV records a real mistake: ``FEN`` is a position in a
rated game, ``Moves[0]`` is the move a human actually played there, and the
remaining moves are the tactic that punished it. Used one ply early -- solver
on the blunderer's side, at the position *before* the mistake -- each row is
a ready-made blunder-check exercise where the tempting move is certified
tempting by the strongest possible evidence: someone played it.

The engine acts as a filter and a co-author, never as the source of truth
for the trap itself:

* reject positions that were already lost (avoiding a blunder there teaches
  nothing) and blunders that were not clearly worse than the best move;
* reject blunders that are not *natural* -- a capture, a check, a promotion,
  or a move a shallow search likes -- because a trap nobody would consider
  makes a worthless puzzle;
* find the safe moves: the best one becomes the puzzle mainline, the others
  become unmarked variations so the session accepts them as ALTERNATIVE
  rather than marking a perfectly good move wrong.

Output is course-format PGN (the blunder as a ``$4`` variation carrying the
game refutation), which the existing loader/session/playback pipeline
consumes with no special handling.
"""

from __future__ import annotations

import csv
import io
import random
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

import chess
import chess.engine
import chess.pgn

from chess_puzzles.pgn.loader import PgnLoader
from chess_puzzles.puzzle import Puzzle


@dataclass(frozen=True, slots=True)
class MiningCriteria:
    rating_min: int = 800
    rating_max: int = 1400
    popularity_min: int = 80
    max_refutation_plies: int = 8
    # Evaluations in centipawns from the blunderer's point of view.
    already_lost_cp: int = -150  # position before the blunder must hold at least this
    blunder_cp: int = -200  # the blunder must be at most this
    min_swing_cp: int = 150  # ... and at least this much worse than the best move
    safe_cp: int = -80  # moves at or above this count as safe
    max_alternatives: int = 2  # extra safe moves kept as unmarked variations
    depth: int = 14
    shallow_depth: int = 6  # naturalness probe for quiet blunders
    shallow_top_n: int = 3
    multipv: int = 5


@dataclass(frozen=True, slots=True)
class MinedPuzzle:
    puzzle_id: str
    pgn_text: str
    rating: int
    themes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Row:
    puzzle_id: str
    board: chess.Board
    blunder: chess.Move
    refutation: tuple[chess.Move, ...]
    rating: int
    themes: tuple[str, ...]
    game_url: str


class BlunderMiner:
    def __init__(self, engine: chess.engine.SimpleEngine, criteria: MiningCriteria) -> None:
        self._engine = engine
        self._criteria = criteria

    def mine(
        self,
        csv_path: str | Path,
        count: int,
        *,
        seed: int | None = None,
        on_progress=None,
        should_stop=None,
    ) -> list[MinedPuzzle]:
        """Scan the CSV from a random offset until ``count`` rows survive
        every filter. ``on_progress(examined, accepted)`` is called per row;
        a truthy ``should_stop()`` ends the scan early, keeping what was
        accepted so far."""
        accepted: list[MinedPuzzle] = []
        examined = 0
        for row in _iter_rows(Path(csv_path), seed=seed):
            if should_stop is not None and should_stop():
                break
            examined += 1
            if on_progress is not None:
                on_progress(examined, len(accepted))
            candidate = self._filter_row(row)
            if candidate is None:
                continue
            puzzle = self._verify_and_build(candidate)
            if puzzle is not None:
                accepted.append(puzzle)
                if len(accepted) >= count:
                    break
        return accepted

    def _filter_row(self, row: dict[str, str]) -> _Row | None:
        """Cheap, engine-free acceptance checks."""
        criteria = self._criteria
        rating = _int(row.get("Rating"))
        popularity = _int(row.get("Popularity"))
        if rating is None or popularity is None:
            return None
        if not (criteria.rating_min <= rating <= criteria.rating_max):
            return None
        if popularity < criteria.popularity_min:
            return None
        moves = row.get("Moves", "").split()
        if len(moves) < 2 or len(moves) - 1 > criteria.max_refutation_plies:
            return None
        try:
            board = chess.Board(row.get("FEN", ""))
            parsed = [chess.Move.from_uci(uci) for uci in moves]
        except ValueError:
            return None
        blunder = parsed[0]
        if blunder not in board.legal_moves:
            return None
        return _Row(
            puzzle_id=row.get("PuzzleId", "").strip(),
            board=board,
            blunder=blunder,
            refutation=tuple(parsed[1:]),
            rating=rating,
            themes=tuple(row.get("Themes", "").split()),
            game_url=row.get("GameUrl", "").strip(),
        )

    def _verify_and_build(self, row: _Row) -> MinedPuzzle | None:
        """Engine checks; returns the built puzzle when everything holds."""
        criteria = self._criteria
        board = row.board
        side = board.turn

        if not self._blunder_is_natural(board, row.blunder):
            return None

        infos = self._engine.analyse(
            board,
            chess.engine.Limit(depth=criteria.depth),
            multipv=criteria.multipv,
        )
        scored: list[tuple[chess.Move, int]] = []
        for info in infos:
            pv = info.get("pv")
            score = info.get("score")
            if not pv or score is None:
                continue
            scored.append((pv[0], score.pov(side).score(mate_score=10_000)))
        if not scored:
            return None

        best_move, best_cp = scored[0]
        if best_cp < criteria.already_lost_cp:
            return None  # already lost: nothing to save

        # The blunder is usually natural enough to appear in the multipv set;
        # only fall back to a dedicated (extra engine call) evaluation when
        # it does not.
        blunder_cp = next((cp for move, cp in scored if move == row.blunder), None)
        if blunder_cp is None:
            blunder_cp = self._eval_after(board, row.blunder, side)
        if blunder_cp > criteria.blunder_cp or best_cp - blunder_cp < criteria.min_swing_cp:
            return None
        if best_move == row.blunder:
            return None  # deep engine disagrees with the puzzle: drop it

        safe = [(move, cp) for move, cp in scored if cp >= criteria.safe_cp and move != row.blunder]
        if not safe:
            return None
        alternatives = [move for move, _ in safe[1 : 1 + criteria.max_alternatives]]
        return MinedPuzzle(
            puzzle_id=row.puzzle_id,
            pgn_text=_build_pgn(row, safe_move=safe[0][0], alternatives=alternatives),
            rating=row.rating,
            themes=row.themes,
        )

    def _blunder_is_natural(self, board: chess.Board, blunder: chess.Move) -> bool:
        """A trap nobody would consider is not a trap. Forcing-looking moves
        pass outright; quiet ones must appear in a shallow search's top picks
        (what a quick glance would consider)."""
        if board.is_capture(blunder) or board.gives_check(blunder) or blunder.promotion:
            return True
        criteria = self._criteria
        infos = self._engine.analyse(
            board,
            chess.engine.Limit(depth=criteria.shallow_depth),
            multipv=criteria.shallow_top_n,
        )
        return any(info.get("pv") and info["pv"][0] == blunder for info in infos)

    def _eval_after(self, board: chess.Board, move: chess.Move, pov: chess.Color) -> int:
        after = board.copy(stack=False)
        after.push(move)
        info = self._engine.analyse(after, chess.engine.Limit(depth=self._criteria.depth))
        return info["score"].pov(pov).score(mate_score=10_000)


def mined_to_puzzles(mined: Sequence[MinedPuzzle]) -> list[Puzzle]:
    """Convert mined puzzles to app puzzles by round-tripping their PGN
    through the real loader, so a generated deck is exactly what importing
    the same PGN file would produce."""
    text = combined_pgn(mined)
    return PgnLoader().load(io.StringIO(text))


def combined_pgn(mined: Sequence[MinedPuzzle]) -> str:
    return "\n\n".join(puzzle.pgn_text for puzzle in mined) + "\n"


def _build_pgn(row: _Row, safe_move: chess.Move, alternatives: list[chess.Move]) -> str:
    game = chess.pgn.Game()
    game.setup(row.board)
    side_name = "White" if row.board.turn == chess.WHITE else "Black"
    game.headers["Event"] = "Blunder check"
    game.headers["White"] = f"Blunder check {row.puzzle_id}"
    game.headers["Black"] = f"{side_name} to move"
    game.headers["Result"] = "*"
    game.headers["PuzzleSide"] = side_name
    game.headers["PuzzleId"] = row.puzzle_id
    game.headers["Rating"] = str(row.rating)
    if row.themes:
        game.headers["Themes"] = " ".join(row.themes)
    if row.game_url:
        game.headers["GameUrl"] = row.game_url
    game.comment = "Find a safe move."

    main = game.add_variation(safe_move)
    main.comment = "Safe."

    trap = game.add_variation(row.blunder)
    trap.nags.add(chess.pgn.NAG_BLUNDER)
    trap.comment = f"The move played in the source game (puzzle rating {row.rating})."
    node = trap
    for move in row.refutation:
        node = node.add_variation(move)
    node.comment = "The refutation played out."

    for move in alternatives:
        alt = game.add_variation(move)
        alt.comment = "Also safe."

    exporter = chess.pgn.StringExporter(headers=True, variations=True, comments=True)
    return game.accept(exporter)


def _iter_rows(path: Path, *, seed: int | None) -> Iterator[dict[str, str]]:
    """Stream CSV rows starting from a random byte offset, wrapping to the
    file start, so repeated runs sample different regions of the database."""
    rng = random.Random(seed)
    file_size = path.stat().st_size
    start_offset = rng.randrange(file_size) if file_size > 0 else 0
    with path.open("rb") as handle:
        header_line = handle.readline().decode("utf-8-sig").rstrip("\r\n")
        headers = next(csv.reader([header_line]))
        data_start = handle.tell()

        def rows_from(offset: int, stop: int | None) -> Iterator[dict[str, str]]:
            handle.seek(offset)
            if offset > data_start:
                handle.readline()  # skip the partial line at the seek point
            while True:
                if stop is not None and handle.tell() >= stop:
                    return
                line = handle.readline()
                if not line:
                    return
                try:
                    values = next(csv.reader([line.decode("utf-8").rstrip("\r\n")]))
                except (StopIteration, UnicodeDecodeError):
                    continue
                yield {
                    header: values[index].strip() if index < len(values) else ""
                    for index, header in enumerate(headers)
                }

        yield from rows_from(max(start_offset, data_start), None)
        if start_offset > data_start:
            yield from rows_from(data_start, start_offset)


def _int(value: str | None) -> int | None:
    try:
        text = str(value).strip()
        return int(text) if text else None
    except (TypeError, ValueError):
        return None
