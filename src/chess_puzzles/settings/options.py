"""Every user preference in one table.

Each row names an :class:`AppSettings` field, the words the user reads, and
the section it belongs to. The Options dialog and the sidebar's quick
toggles both render from this table, so adding a preference is one row here
plus one field on ``AppSettings`` -- there is no second list of labels to
keep in sync.

``kinds`` restricts a row to particular deck kinds. Most preferences apply
everywhere and leave it ``None``; the two repertoire options are the only
ones whose meaning depends on the deck. Restricted rows stay visible and
greyed rather than disappearing, so a preference is always findable where
the user last saw it, and ``SECTION_NOTES`` says why once per section.
"""

from __future__ import annotations

from dataclasses import dataclass

from chess_puzzles.store import DECK_KIND_REPERTOIRE


# Section headings, in the order the dialog shows them. The Options dialog
# gives each one a tab, so a new section is a new tab and nothing else.
INTERFACE = "Interface"
SOLVING = "Solving flow"
REPERTOIRE = "Opening courses"

SECTIONS: tuple[str, ...] = (INTERFACE, SOLVING, REPERTOIRE)

# Shown once at the top of a section whose options do not apply to the open
# course, in place of repeating the reason on every row.
SECTION_NOTES: dict[str, str] = {
    REPERTOIRE: "These apply while an opening course is open.",
}


@dataclass(frozen=True, slots=True)
class Option:
    """One preference, rendered as a checkbox."""

    key: str
    label: str
    help: str
    section: str
    kinds: frozenset[str] | None = None
    # Shown in the sidebar's Training box as well, for the ones worth
    # flipping mid-session without opening a dialog.
    quick: bool = False

    def applies_to(self, deck_kind: str | None) -> bool:
        return self.kinds is None or (deck_kind is not None and deck_kind in self.kinds)


OPTIONS: tuple[Option, ...] = (
    Option(
        key="show_coordinates",
        label="Show coordinates",
        help="File and rank labels along the edge of the board.",
        section=INTERFACE,
    ),
    Option(
        key="show_evaluation_bar",
        label="Show evaluation bar",
        help="The engine's evaluation as a bar beside the board.",
        section=INTERFACE,
    ),
    Option(
        key="show_session_stats",
        label="Show session stats",
        help="Attempted, solved and average time in the status bar.",
        section=INTERFACE,
    ),
    Option(
        key="show_user_notes",
        label="Show notes panel",
        help="Your own notes on the current puzzle, saved as you type.",
        section=INTERFACE,
    ),
    Option(
        key="sound_enabled",
        label="Play sounds",
        help="Move, capture and check sounds.",
        section=INTERFACE,
    ),
    Option(
        key="reflow_comments",
        label="Reflow comment text",
        help=(
            "Join the author's hard line breaks so comments wrap to the panel "
            "instead of breaking mid-sentence. Paragraphs are kept."
        ),
        section=INTERFACE,
        quick=True,
    ),
    Option(
        key="auto_advance",
        label="Advance automatically",
        help="Go to the next puzzle once nothing is waiting for you.",
        section=SOLVING,
        quick=True,
    ),
    Option(
        key="stop_at_comments",
        label="Stop at annotated moves",
        help=(
            "Hold at any move that carries a comment, so there is time to "
            "read it: while you solve, on the last move, and while watching a "
            "line the app plays for you."
        ),
        section=SOLVING,
        quick=True,
    ),
    Option(
        key="show_avoided_mistakes",
        label="Show mistakes I avoided",
        help=(
            "After solving, offer to watch the mistakes the author marked in "
            "this line that you never played."
        ),
        section=SOLVING,
    ),
    Option(
        key="step_through_lines",
        label="Step through played lines one move at a time",
        help=(
            "When the app plays a line for you - a mistake's consequence, or "
            "an opening line's first demonstration - wait for the continue "
            "key at every move, not just the annotated ones. The final "
            "position always waits."
        ),
        section=SOLVING,
    ),
    Option(
        key="start_lines_at_divergence",
        label="Start lines at divergence",
        help=(
            "When the next line shares its opening moves with the previous "
            "one, replay the shared part and start you where they differ."
        ),
        section=REPERTOIRE,
        kinds=frozenset({DECK_KIND_REPERTOIRE}),
    ),
    Option(
        key="demonstrate_new_lines",
        label="Demonstrate new lines first",
        help=(
            "Show a line you have never solved before, then rewind and ask "
            "you to play it back."
        ),
        section=REPERTOIRE,
        kinds=frozenset({DECK_KIND_REPERTOIRE}),
    ),
)


QUICK_OPTIONS: tuple[Option, ...] = tuple(option for option in OPTIONS if option.quick)


def options_in(section: str) -> tuple[Option, ...]:
    return tuple(option for option in OPTIONS if option.section == section)
