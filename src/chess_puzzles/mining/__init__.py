"""Generation of training content from external sources."""

from chess_puzzles.mining.blunder_miner import (
    BlunderMiner,
    MinedPuzzle,
    MiningCriteria,
    combined_pgn,
    mined_to_puzzles,
)
from chess_puzzles.mining.settings import (
    MiningDialogSettings,
    load_mining_settings,
    save_mining_settings,
)

__all__ = [
    "BlunderMiner",
    "MinedPuzzle",
    "MiningCriteria",
    "MiningDialogSettings",
    "combined_pgn",
    "load_mining_settings",
    "mined_to_puzzles",
    "save_mining_settings",
]
