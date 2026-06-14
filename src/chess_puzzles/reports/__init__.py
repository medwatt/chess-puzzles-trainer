"""Read-side reports derived from raw user data."""

from chess_puzzles.reports.formatting import format_duration_ms
from chess_puzzles.reports.model import AttemptSummary
from chess_puzzles.reports.queries import attempt_summary

__all__ = ["AttemptSummary", "attempt_summary", "format_duration_ms"]
