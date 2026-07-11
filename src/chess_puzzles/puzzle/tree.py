"""Variation tree parsed from a puzzle's stored PGN.

The content store keeps each puzzle's full PGN (``pgn_text``) verbatim, so
every variation an author wrote -- alternative lines, annotated mistakes and
their refutations -- is already persisted even though ``Puzzle.moves`` holds
only the drilled line. This module turns that text back into a tree the
solving session can consult when the user deviates from the expected move.

Semantics follow standard PGN annotation glyphs: a variation whose first move
carries ``?`` ($2), ``??`` ($4) or ``?!`` ($6) is a mistake to punish, and the
rest of that variation is its refutation. Any other sibling variation is an
acceptable alternative. Trees are derived on demand and never persisted; a
puzzle without variations (or without PGN at all) simply has no tree, which
leaves session behavior exactly as it was.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import chess
import chess.pgn


MISTAKE_NAGS = frozenset(
    {
        chess.pgn.NAG_MISTAKE,  # $2  ?
        chess.pgn.NAG_BLUNDER,  # $4  ??
        chess.pgn.NAG_DUBIOUS_MOVE,  # $6  ?!
    }
)


@dataclass(frozen=True, slots=True)
class TreeNode:
    """One move in the variation tree. ``move`` is None only on the root."""

    move: chess.Move | None
    is_mistake: bool
    comment: str
    children: tuple["TreeNode", ...]

    def child(self, move: chess.Move) -> "TreeNode | None":
        for node in self.children:
            if node.move == move:
                return node
        return None


@dataclass(frozen=True, slots=True)
class Refutation:
    """Why a mistake-marked move fails: the punishing line and its commentary.

    ``comments[0]`` annotates the mistake move itself; ``comments[i]``
    annotates ``line[i - 1]``, mirroring the comment convention used for
    puzzle mainlines.
    """

    move: chess.Move
    line: tuple[chess.Move, ...]
    comments: tuple[str, ...]


class MoveTree:
    """Lookup structure over a puzzle's variations.

    The session keeps a :class:`TreeNode` cursor that it advances with every
    move actually played; classification of a deviating move is then a plain
    child lookup on the cursor.
    """

    def __init__(self, root: TreeNode) -> None:
        self.root = root

    @property
    def has_branches(self) -> bool:
        return _has_branches(self.root)

    @classmethod
    def from_pgn_text(cls, pgn_text: str, initial_fen: str) -> "MoveTree | None":
        """Build a tree, or None when the PGN is absent, unparseable, or
        starts from a different position than the puzzle (in which case its
        variations do not describe the puzzle's board)."""
        if not pgn_text.strip():
            return None
        try:
            game = chess.pgn.read_game(io.StringIO(pgn_text))
        except Exception:
            return None
        if game is None:
            return None
        try:
            if game.board().fen() != chess.Board(initial_fen).fen():
                return None
        except ValueError:
            return None
        return cls(_build_node(game))

    @staticmethod
    def refutation_of(node: TreeNode) -> Refutation:
        """The principal continuation after a mistake move, with comments."""
        assert node.move is not None
        line: list[chess.Move] = []
        comments = [node.comment]
        current = node
        while current.children:
            current = current.children[0]
            assert current.move is not None
            line.append(current.move)
            comments.append(current.comment)
        return Refutation(move=node.move, line=tuple(line), comments=tuple(comments))


def _build_node(game_node: chess.pgn.GameNode) -> TreeNode:
    # Null moves ("--") hang lesson text off a static position; they and
    # everything after them are not playable content, so such children are
    # dropped -- matching how the loader truncates mainlines at null moves.
    children = tuple(
        _build_node(child) for child in game_node.variations if child.move != chess.Move.null()
    )
    move = game_node.move if not isinstance(game_node, chess.pgn.Game) else None
    is_mistake = bool(MISTAKE_NAGS & game_node.nags) if move is not None else False
    return TreeNode(
        move=move,
        is_mistake=is_mistake,
        comment=game_node.comment.strip(),
        children=children,
    )


def _has_branches(node: TreeNode) -> bool:
    if len(node.children) > 1:
        return True
    return any(_has_branches(child) for child in node.children)
