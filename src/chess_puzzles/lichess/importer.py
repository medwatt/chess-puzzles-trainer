from __future__ import annotations

import csv
import random
from collections.abc import Callable
from dataclasses import dataclass, fields
from pathlib import Path

import chess

from chess_puzzles.puzzle import Puzzle
from chess_puzzles.store.identity import puzzle_fingerprint


DEFAULT_LICHESS_DATABASE_NAME = "Lichess filtered database"
DEFAULT_LICHESS_DATABASE_FILENAME = "lichess_filtered_database.cpdb"

# How multiple selected themes combine.
THEME_MODE_ANY = "any"
THEME_MODE_ALL = "all"


@dataclass(slots=True, frozen=True)
class LichessImportCriteria:
    sample_size: int
    rating_min: int = 0
    rating_max: int = 3000
    popularity_min: int = 0
    # Every default below leaves its filter open, so a caller that sets only
    # what it cares about (the arena refill) is unaffected by new fields.
    rating_deviation_max: int = 500
    nb_plays_min: int = 0
    # Counted in *your* moves: the CSV's move list opens with the opponent's
    # setup move, so a 2-ply row is a one-move puzzle.
    moves_min: int = 1
    moves_max: int = 13
    # Themes and openings are independent dimensions: across them every
    # constraint must hold, and an empty dimension constrains nothing.
    # Within themes, ``theme_mode`` chooses between alternatives and
    # conjunction; openings are always alternatives.
    themes: tuple[str, ...] = ()
    theme_mode: str = THEME_MODE_ANY
    themes_excluded: tuple[str, ...] = ()
    openings: tuple[str, ...] = ()


class LichessCsvImporter:
    def sample_puzzles(
        self,
        csv_path: str | Path,
        criteria: LichessImportCriteria,
        seed: int | None = None,
        *,
        exclude_ids: frozenset[str] | set[str] = frozenset(),
        row_budget: int | None = None,
        on_progress: Callable[[int, int], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> list[Puzzle]:
        """Sample matching puzzles starting from a random offset.

        ``exclude_ids`` skips already-known puzzles (arena dedupe).
        ``row_budget`` caps the total rows scanned so a sparse filter degrades
        to a short sample instead of an unbounded read (arena refills run on
        the UI thread).

        ``on_progress(examined, accepted)`` is called per row and a truthy
        ``should_stop()`` ends the scan early, keeping what was accepted --
        the same contract as ``BlunderMiner.mine``. A narrow filter can read
        the whole file, so any caller on the UI thread wants both.
        """
        path = Path(csv_path)
        rng = random.Random(seed) if seed is not None else random.Random()
        file_size = path.stat().st_size
        start_offset = rng.randrange(file_size) if file_size > 0 else 0
        budget = [row_budget] if row_budget is not None else None
        # Shared across both passes so progress counts the whole scan.
        examined = [0]
        puzzles = self._scan_from_offset(
            path, start_offset, criteria, exclude_ids=exclude_ids, budget=budget,
            examined=examined, on_progress=on_progress, should_stop=should_stop,
        )
        stopped = should_stop is not None and should_stop()
        if not stopped and len(puzzles) < criteria.sample_size and start_offset > 0:
            puzzles.extend(
                self._scan_from_offset(
                    path,
                    0,
                    criteria,
                    stop_offset=start_offset,
                    exclude_ids=exclude_ids,
                    budget=budget,
                    examined=examined,
                    on_progress=on_progress,
                    should_stop=should_stop,
                    accepted_before=len(puzzles),
                )
            )
        return puzzles[: criteria.sample_size]

    def default_description(self, criteria: LichessImportCriteria) -> str:
        """Describe only the filters that were actually narrowed.

        Derived from the dataclass rather than listed by hand: anything left
        at its open default says nothing, and a filter added later describes
        itself without being wired in here."""
        wide_open = LichessImportCriteria(sample_size=criteria.sample_size)
        filters: list[str] = []
        for field in fields(criteria):
            if field.name == "sample_size":
                continue
            value = getattr(criteria, field.name)
            if value == getattr(wide_open, field.name):
                continue
            label = field.name.replace("_", " ")
            filters.append(
                f"{label}: {', '.join(value)}" if isinstance(value, tuple) else f"{label} {value}"
            )
        suffix = f" ({'; '.join(filters)})" if filters else ""
        return f"Imported from Lichess CSV with {criteria.sample_size} sampled puzzles{suffix}."

    def _scan_from_offset(
        self,
        path: Path,
        start_offset: int,
        criteria: LichessImportCriteria,
        *,
        stop_offset: int | None = None,
        exclude_ids: frozenset[str] | set[str] = frozenset(),
        budget: list[int] | None = None,
        examined: list[int] | None = None,
        on_progress: Callable[[int, int], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
        accepted_before: int = 0,
    ) -> list[Puzzle]:
        # ``budget`` is a single-item list so the remaining row allowance is
        # shared across the wrap-around second scan.
        puzzles: list[Puzzle] = []
        with path.open("rb") as raw_handle:
            header_line = raw_handle.readline()
            if not header_line:
                return puzzles
            headers = self._parse_csv_row(header_line.decode("utf-8-sig").rstrip("\r\n"))
            raw_handle.seek(start_offset)
            if start_offset > 0:
                raw_handle.readline()
            while True:
                if stop_offset is not None and raw_handle.tell() >= stop_offset:
                    break
                if budget is not None:
                    if budget[0] <= 0:
                        break
                    budget[0] -= 1
                if should_stop is not None and should_stop():
                    break
                line = raw_handle.readline()
                if not line:
                    break
                if examined is not None:
                    examined[0] += 1
                row = self._row_from_line(headers, line)
                if (
                    row is not None
                    and self._row_matches(row, criteria)
                    and row.get("PuzzleId", "").strip() not in exclude_ids
                ):
                    puzzle = self._puzzle_from_row(row, len(puzzles) + 1, criteria.themes)
                    if puzzle is not None:
                        puzzles.append(puzzle)
                accepted = accepted_before + len(puzzles)
                # Reported after the row is accepted, so the final callback
                # carries the finished count rather than one short of it.
                if on_progress is not None and examined is not None:
                    on_progress(examined[0], accepted)
                # Counted against what the wrap-around pass already accepted,
                # not this pass alone: otherwise the second pass hunts for a
                # whole fresh sample instead of just the shortfall.
                if accepted >= criteria.sample_size:
                    break
        return puzzles

    def _row_from_line(self, headers: list[str], line: bytes) -> dict[str, str] | None:
        values = self._parse_csv_row(line.decode("utf-8").rstrip("\r\n"))
        if not values:
            return None
        return {header: values[index].strip() if index < len(values) else "" for index, header in enumerate(headers)}

    def _parse_csv_row(self, text: str) -> list[str]:
        try:
            return next(csv.reader([text]))
        except StopIteration:
            return []

    def _puzzle_from_row(self, row: dict[str, str], source_index: int, selected_themes: tuple[str, ...]) -> Puzzle | None:
        initial_fen = row.get("FEN", "").strip()
        moves = self._parse_moves(row.get("Moves", ""))
        if not initial_fen or not moves:
            return None
        row_themes = tuple(token for token in row.get("Themes", "").split() if token)
        puzzle_theme = self._selected_theme(row_themes, selected_themes)
        puzzle_id = row.get("PuzzleId", "").strip() or self._fallback_puzzle_id(initial_fen, moves)
        headers = {"Event": "Lichess puzzle", "Source": "Lichess CSV", "PuzzleId": puzzle_id}
        for key in ("Rating", "Popularity", "RatingDeviation", "NbPlays", "GameUrl", "OpeningTags"):
            if value := row.get(key, "").strip():
                headers[key] = value
        if row_themes:
            headers["Themes"] = " ".join(row_themes)
        return Puzzle(
            title=f"Lichess {puzzle_id}",
            initial_fen=initial_fen,
            moves=moves,
            headers=headers,
            puzzle_id=puzzle_id,
            ordinal=source_index,
            theme=puzzle_theme,
            skip_first_move=True,
        )

    def _row_matches(self, row: dict[str, str], criteria: LichessImportCriteria) -> bool:
        rating = self._int_or_none(row.get("Rating"))
        popularity = self._int_or_none(row.get("Popularity"))
        if rating is None or popularity is None:
            return False
        if rating < criteria.rating_min or rating > criteria.rating_max or popularity < criteria.popularity_min:
            return False
        deviation = self._int_or_none(row.get("RatingDeviation"))
        if deviation is not None and deviation > criteria.rating_deviation_max:
            return False
        plays = self._int_or_none(row.get("NbPlays"))
        if plays is not None and plays < criteria.nb_plays_min:
            return False
        if criteria.moves_min > 1 or criteria.moves_max < 13:
            # Halved, not counted: the leading setup move is the opponent's.
            moves = len(row.get("Moves", "").split()) // 2
            if moves < criteria.moves_min or moves > criteria.moves_max:
                return False
        if criteria.themes or criteria.themes_excluded:
            row_themes = row.get("Themes", "").split()
            if criteria.themes:
                matched = (
                    all(theme in row_themes for theme in criteria.themes)
                    if criteria.theme_mode == THEME_MODE_ALL
                    else any(theme in row_themes for theme in criteria.themes)
                )
                if not matched:
                    return False
            if any(theme in row_themes for theme in criteria.themes_excluded):
                return False
        if criteria.openings:
            # Each tagged puzzle lists its family and its variation, so an exact
            # match against either is enough to catch a whole family.
            row_openings = row.get("OpeningTags", "").split()
            if not any(opening in row_openings for opening in criteria.openings):
                return False
        return True

    def _parse_moves(self, moves_text: str) -> tuple[chess.Move, ...]:
        moves: list[chess.Move] = []
        for move_text in moves_text.split():
            try:
                moves.append(chess.Move.from_uci(move_text))
            except ValueError:
                return ()
        return tuple(moves)

    def _selected_theme(self, row_themes: tuple[str, ...], selected_themes: tuple[str, ...]) -> str:
        for selected in selected_themes:
            if selected in row_themes:
                return selected
        return row_themes[0] if row_themes else ""

    def _int_or_none(self, value: str | None) -> int | None:
        try:
            text = str(value).strip()
            return int(text) if text else None
        except (TypeError, ValueError):
            return None

    def _fallback_puzzle_id(self, initial_fen: str, moves: tuple[chess.Move, ...]) -> str:
        return puzzle_fingerprint(initial_fen, tuple(move.uci() for move in moves))
