#!/usr/bin/env python3
"""Refresh the shipped Lichess theme and opening vocabularies from a puzzle CSV.

Lichess adds themes and openings over time, and the puzzle database is
republished regularly. Nothing in the app notices when that happens: an
unknown tag is simply never offered in the import dialog, and one written by
hand into ``lichess.json`` is dropped on load. This script is how that drift
gets found.

The two files are maintained differently, because they are different kinds of
list:

``themes.txt`` is curated. Its order is meaningful -- phase, then endgame
types, then motifs, then named mates, then length, then player level -- which
no scan can reconstruct. So it is only ever *appended* to, and entries that
have vanished from the data are reported rather than deleted.

``openings.txt`` is mechanical: ~1,600 alphabetical tags with no grouping, so
it is regenerated wholesale.

Usage:
    python scripts/refresh_lichess_vocabulary.py            # use the app's configured CSV
    python scripts/refresh_lichess_vocabulary.py --csv PATH
    python scripts/refresh_lichess_vocabulary.py --check    # report drift, write nothing
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

# Run from a checkout without installing the package first.
_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from chess_puzzles.lichess.vocabulary import LICHESS_OPENINGS, LICHESS_THEMES  # noqa: E402
from chess_puzzles.settings.repository import SettingsRepository  # noqa: E402


VOCABULARY_DIR = _SRC / "chess_puzzles" / "lichess"

# A CSV that yields far fewer tags than we already ship is a partial or
# truncated download, not a Lichess deletion. Refuse rather than silently
# throw away a working vocabulary.
SHRINK_LIMIT = 0.9


def scan(csv_path: Path) -> tuple[set[str], set[str]]:
    """Collect every theme and opening tag in one pass over the CSV."""
    themes: set[str] = set()
    openings: set[str] = set()
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            raise SystemExit(f"{csv_path} is empty") from None
        try:
            theme_index = header.index("Themes")
            opening_index = header.index("OpeningTags")
        except ValueError as exc:
            raise SystemExit(f"{csv_path} is not a Lichess puzzle export: {exc}") from None
        for row in reader:
            if len(row) > theme_index and row[theme_index]:
                themes.update(row[theme_index].split())
            if len(row) > opening_index and row[opening_index]:
                openings.update(row[opening_index].split())
    return themes, openings


def report(label: str, shipped: set[str], found: set[str]) -> tuple[list[str], list[str]]:
    missing = sorted(found - shipped)
    stale = sorted(shipped - found)
    print(f"\n{label}: {len(shipped)} shipped, {len(found)} in data")
    for name in missing:
        print(f"   + {name}   (in the data, not offered)")
    for name in stale:
        print(f"   - {name}   (offered, not in this CSV)")
    if not missing and not stale:
        print("   up to date")
    return missing, stale


def append_themes(missing: list[str]) -> None:
    """Append new themes, leaving the curated grouping alone."""
    path = VOCABULARY_DIR / "themes.txt"
    text = path.read_text(encoding="utf-8").rstrip("\n")
    text += "\n# Added by refresh_lichess_vocabulary.py -- move into the right group.\n"
    text += "\n".join(missing) + "\n"
    path.write_text(text, encoding="utf-8")
    print(f"\nappended {len(missing)} theme(s) to {path.name}; move them into their groups")


def check_not_truncated(found: set[str], *, force: bool) -> None:
    """Validate before any file is touched, so a bad CSV changes nothing."""
    if len(found) < len(LICHESS_OPENINGS) * SHRINK_LIMIT and not force:
        raise SystemExit(
            f"refusing to shrink openings.txt from {len(LICHESS_OPENINGS)} to {len(found)} "
            f"tags; pass --force if the CSV really is authoritative"
        )


def write_openings(found: set[str]) -> None:
    path = VOCABULARY_DIR / "openings.txt"
    path.write_text(
        "# Lichess opening tags, extracted from the puzzle database.\n"
        "# Each tagged puzzle carries its family and its variation, so selecting a\n"
        "# family (e.g. Sicilian_Defense) matches every variation under it.\n"
        "# Regenerate with scripts/refresh_lichess_vocabulary.py\n"
        + "\n".join(sorted(found))
        + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(found)} opening tag(s) to {path.name}")


def resolve_csv(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    configured = SettingsRepository().load().lichess_csv_path
    if not configured:
        raise SystemExit("no CSV given and no lichess_csv_path in settings; pass --csv")
    return Path(configured).expanduser()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--csv", help="Lichess puzzle CSV (default: the path configured in the app)")
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    parser.add_argument("--force", action="store_true", help="allow openings.txt to shrink")
    args = parser.parse_args()

    csv_path = resolve_csv(args.csv)
    if not csv_path.is_file():
        raise SystemExit(f"not a file: {csv_path}")

    print(f"scanning {csv_path} ...")
    started = time.monotonic()
    themes, openings = scan(csv_path)
    print(f"scanned in {time.monotonic() - started:.0f}s")

    missing_themes, _ = report("themes", set(LICHESS_THEMES), themes)
    missing_openings, stale_openings = report("openings", set(LICHESS_OPENINGS), openings)

    drifted = bool(missing_themes or missing_openings or stale_openings)
    if args.check:
        print("\ndrift found" if drifted else "\nno drift")
        return 1 if drifted else 0
    if not drifted:
        print("\nnothing to do")
        return 0
    # Validate everything before writing anything: a truncated CSV must not
    # leave themes.txt updated and openings.txt not.
    check_not_truncated(openings, force=args.force)
    if missing_themes:
        append_themes(missing_themes)
    if missing_openings or stale_openings:
        write_openings(openings)
    print("\nre-run with --check to confirm, and commit the updated file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
