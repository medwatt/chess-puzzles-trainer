from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path

import chess

from chess_puzzles.puzzle import Puzzle
from chess_puzzles.store.identity import puzzle_fingerprint


DEFAULT_LICHESS_DATABASE_NAME = "Lichess filtered database"
DEFAULT_LICHESS_DATABASE_FILENAME = "lichess_filtered_database.cpdb"


@dataclass(slots=True, frozen=True)
class LichessImportCriteria:
    sample_size: int
    rating_min: int = 0
    rating_max: int = 3000
    popularity_min: int = 0
    themes: tuple[str, ...] = ()


class LichessCsvImporter:
    def sample_puzzles(self, csv_path: str | Path, criteria: LichessImportCriteria, seed: int | None = None) -> list[Puzzle]:
        path = Path(csv_path)
        rng = random.Random(seed) if seed is not None else random.Random()
        file_size = path.stat().st_size
        start_offset = rng.randrange(file_size) if file_size > 0 else 0
        puzzles = self._scan_from_offset(path, start_offset, criteria)
        if len(puzzles) < criteria.sample_size and start_offset > 0:
            puzzles.extend(self._scan_from_offset(path, 0, criteria, stop_offset=start_offset))
        return puzzles[: criteria.sample_size]

    def default_description(self, criteria: LichessImportCriteria) -> str:
        filters: list[str] = []
        if criteria.rating_min > 0 or criteria.rating_max < 3000:
            filters.append(f"rating {criteria.rating_min}-{criteria.rating_max}")
        if criteria.popularity_min > 0:
            filters.append(f"popularity >= {criteria.popularity_min}")
        if criteria.themes:
            filters.append(f"themes: {', '.join(criteria.themes)}")
        suffix = f" ({'; '.join(filters)})" if filters else ""
        return f"Imported from Lichess CSV with {criteria.sample_size} sampled puzzles{suffix}."

    def _scan_from_offset(
        self,
        path: Path,
        start_offset: int,
        criteria: LichessImportCriteria,
        *,
        stop_offset: int | None = None,
    ) -> list[Puzzle]:
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
                line = raw_handle.readline()
                if not line:
                    break
                row = self._row_from_line(headers, line)
                if row is None or not self._row_matches(row, criteria):
                    continue
                puzzle = self._puzzle_from_row(row, len(puzzles) + 1, criteria.themes)
                if puzzle is not None:
                    puzzles.append(puzzle)
                if len(puzzles) >= criteria.sample_size:
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
        for key in ("Rating", "Popularity", "RatingDeviation", "NbPlays", "GameUrl"):
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
        row_themes = tuple(token for token in row.get("Themes", "").split() if token)
        return not criteria.themes or any(theme in row_themes for theme in criteria.themes)

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
