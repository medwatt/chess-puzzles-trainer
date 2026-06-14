from __future__ import annotations

import hashlib


def puzzle_fingerprint(initial_fen: str, moves: tuple[str, ...], comments: tuple[str, ...] = ()) -> str:
    """Stable content identity for a puzzle.

    Tactical puzzles are identified by position + solution so comments, titles,
    and importer metadata can change without orphaning personal data. Move-free
    study pages have no solution, so their comments are part of the exercise
    identity.
    """
    sections = [initial_fen.strip(), "\n".join(moves)]
    if not moves:
        sections.append("\n".join(comment.strip() for comment in comments if comment.strip()))
    body = "\n\x00".join(sections)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()
