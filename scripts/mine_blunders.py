#!/usr/bin/env python3
"""Generate an "avoid the blunder" deck from the Lichess puzzle CSV.

Defaults (CSV path, engine, output directory) come from the app's own
configuration; every one can be overridden. Produces both a course-format
.pgn (inspectable, shareable) and a ready-to-open .cpdb.

Example:
    python scripts/mine_blunders.py --count 50 --rating-min 900 --rating-max 1400
"""

from __future__ import annotations

import argparse
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import chess.engine

from chess_puzzles.engine.config import load_engine_config
from chess_puzzles.lichess.settings import load_lichess_settings
from chess_puzzles.mining import BlunderMiner, MiningCriteria, combined_pgn, mined_to_puzzles
from chess_puzzles.settings.repository import SettingsRepository
from chess_puzzles.store import ContentDatabase, ContentMeta, now_iso


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, default=None, help="Lichess puzzle CSV (default: app config)")
    parser.add_argument("--engine", type=Path, default=None, help="UCI engine (default: app config)")
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--rating-min", type=int, default=800)
    parser.add_argument("--rating-max", type=int, default=1400)
    parser.add_argument("--depth", type=int, default=14)
    parser.add_argument("--max-refutation-plies", type=int, default=8)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None, help="Output basename (default: app database dir)")
    args = parser.parse_args()

    csv_path = args.csv or Path(load_lichess_settings().csv_path)
    if not csv_path.is_file():
        parser.error(f"CSV not found: {csv_path}")

    engine_path = args.engine
    threads = 2
    if engine_path is None:
        config = load_engine_config()
        default = config.default_engine
        if default is None:
            parser.error("no engine configured in the app and no --engine given")
        engine_path = Path(default.command)
        threads = default.threads
    if not engine_path.is_file():
        parser.error(f"engine not found: {engine_path}")

    out_base = args.out
    if out_base is None:
        directory = SettingsRepository().load().default_database_directory or "."
        stamp = time.strftime("%Y%m%d-%H%M%S")
        out_base = Path(directory) / f"blunder_check_{args.rating_min}-{args.rating_max}_{stamp}"
    out_base.parent.mkdir(parents=True, exist_ok=True)

    criteria = MiningCriteria(
        rating_min=args.rating_min,
        rating_max=args.rating_max,
        depth=args.depth,
        max_refutation_plies=args.max_refutation_plies,
    )

    started = time.monotonic()

    def progress(examined: int, accepted: int) -> None:
        if examined % 200 == 0:
            print(f"  examined {examined} rows, accepted {accepted}...", flush=True)

    engine = chess.engine.SimpleEngine.popen_uci(str(engine_path))
    try:
        engine.configure({"Threads": threads})
        miner = BlunderMiner(engine, criteria)
        mined = miner.mine(csv_path, args.count, seed=args.seed, on_progress=progress)
    finally:
        engine.quit()
    elapsed = time.monotonic() - started
    if not mined:
        print("No puzzles survived the filters.")
        return 1

    pgn_path = out_base.with_suffix(".pgn")
    pgn_path.write_text(combined_pgn(mined), encoding="utf-8")

    puzzles = mined_to_puzzles(mined)
    if len(puzzles) != len(mined):
        print(f"WARNING: loader kept {len(puzzles)} of {len(mined)} generated games")
    cpdb_path = out_base.with_suffix(".cpdb")
    meta = ContentMeta(
        database_id=str(uuid.uuid4()),
        name=out_base.stem,
        description=(
            f"Generated blunder-check deck: rating {args.rating_min}-{args.rating_max}, "
            f"{len(puzzles)} puzzles, engine depth {args.depth}."
        ),
        source_kind="mined",
        source_path=str(csv_path),
        created_at=now_iso(),
        updated_at=now_iso(),
    )
    ContentDatabase.create(cpdb_path, meta, puzzles).close()

    print(f"Accepted {len(mined)} puzzles in {elapsed:.0f}s")
    print(f"  PGN:  {pgn_path}")
    print(f"  Deck: {cpdb_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
