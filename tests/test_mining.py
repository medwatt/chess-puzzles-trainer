from __future__ import annotations

from io import StringIO

import chess

from chess_puzzles.mining.blunder_miner import _Row, _build_pgn
from chess_puzzles.mining.settings import MiningDialogSettings, load_mining_settings, save_mining_settings
from chess_puzzles.pgn import PgnLoader
from chess_puzzles.puzzle import MoveResult, PuzzleSession


def _row() -> _Row:
    # After 1.e4 e5 2.Nf3 Nc6 3.Bc4: Black to move. 3...Nd4?? loses a pawn
    # (structurally a fine stand-in for a mined row; evals are irrelevant to
    # the PGN builder).
    board = chess.Board("r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3")
    return _Row(
        puzzle_id="test1",
        board=board,
        blunder=chess.Move.from_uci("c6d4"),
        refutation=(chess.Move.from_uci("f3e5"),),
        rating=1100,
        themes=("hangingPiece", "opening"),
        game_url="https://lichess.org/abc",
    )


def test_built_pgn_round_trips_through_loader_and_session() -> None:
    pgn_text = _build_pgn(
        _row(),
        safe_move=chess.Move.from_uci("g8f6"),
        alternatives=[chess.Move.from_uci("f8c5")],
    )

    puzzles = PgnLoader().load(StringIO(pgn_text))
    assert len(puzzles) == 1
    puzzle = puzzles[0]
    assert puzzle.player_color == chess.BLACK
    assert not puzzle.skip_first_move
    assert puzzle.moves == (chess.Move.from_uci("g8f6"),)
    assert puzzle.comments[0] == "Find a safe move."
    assert puzzle.headers["Rating"] == "1100"

    # The certified trap punishes; the extra safe move completes as a leaf.
    session = PuzzleSession(puzzle, chess.BLACK)
    assert session.play_user_move(chess.Move.from_uci("c6d4")) is MoveResult.BLUNDER
    assert [m.uci() for m in session.last_refutation.line] == ["f3e5"]
    assert session.play_user_move(chess.Move.from_uci("f8c5")) is MoveResult.COMPLETE

    session.reset()
    assert session.play_user_move(chess.Move.from_uci("g8f6")) is MoveResult.COMPLETE


def test_mining_settings_round_trip(tmp_path) -> None:
    path = tmp_path / "mining.json"
    assert load_mining_settings(path) == MiningDialogSettings()
    saved = MiningDialogSettings(csv_path="/x.csv", count=25, rating_min=1000, rating_max=1500)
    save_mining_settings(saved, path)
    assert load_mining_settings(path) == saved
