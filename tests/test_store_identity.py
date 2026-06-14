from __future__ import annotations

from chess_puzzles.store.identity import puzzle_fingerprint


FEN = "8/8/8/8/8/8/4K3/7k w - - 0 1"


def test_fingerprint_is_64_hex_chars() -> None:
    digest = puzzle_fingerprint(FEN, ("e2e3",))
    assert len(digest) == 64
    assert all(char in "0123456789abcdef" for char in digest)


def test_fingerprint_is_deterministic() -> None:
    assert puzzle_fingerprint(FEN, ("e2e3",)) == puzzle_fingerprint(FEN, ("e2e3",))


def test_fingerprint_is_stable_across_releases() -> None:
    # The fingerprint is the cross-store key that links saved progress to puzzles.
    # If it changes, every user's attempts/notes/favorites silently orphan, so
    # these golden values must not change without a migration.
    assert puzzle_fingerprint(FEN, ("e2e3", "e1e2")) == (
        "128f7a63fa2ab6d58e1e4ddb3d5225eba59f1ee86e2ceeed6da3ddab94838f6a"
    )
    assert puzzle_fingerprint(FEN, (), ("lesson one",)) == (
        "93b09566f9bfeb3ed3fd8f34e4e1f3665270fc61660b06f6101c7fee42c8387c"
    )


def test_fingerprint_differs_on_fen_or_move_change() -> None:
    assert puzzle_fingerprint(FEN, ("e2e3",)) != puzzle_fingerprint(FEN, ("e2e4",))
    assert puzzle_fingerprint(FEN, ("e2e3",)) != puzzle_fingerprint(FEN.replace("0 1", "0 2"), ("e2e3",))


def test_fingerprint_differs_on_comment_change() -> None:
    # Move-free study pages are distinguished by their text.
    assert puzzle_fingerprint(FEN, (), ("lesson one",)) != puzzle_fingerprint(FEN, (), ("lesson two",))
    assert puzzle_fingerprint(FEN, ()) != puzzle_fingerprint(FEN, (), ("note",))


def test_fingerprint_ignores_comments_when_moves_exist() -> None:
    assert puzzle_fingerprint(FEN, ("e2e3",), ("old note",)) == puzzle_fingerprint(
        FEN, ("e2e3",), ("new note",)
    )
