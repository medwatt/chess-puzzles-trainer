"""The numeric import filters, declared once.

Each entry drives three things that used to be written out by hand and drift
apart: the persisted settings field, the dialog slider, and which tab it
appears under. Adding a filter is four small edits, none of them wiring:

1. add a row here,
2. add the field to :class:`LichessImportSettings`,
3. add the field to :class:`LichessImportCriteria`,
4. add one guard clause to ``LichessCsvImporter._row_matches``.

Themes and openings are not here: they are vocabularies rather than ranges,
and they get their own tabs.
"""

from __future__ import annotations

from dataclasses import dataclass


# Tab titles, in display order. Filters name one of these.
TAB_DIFFICULTY = "Difficulty"
TAB_QUALITY = "Quality"
TAB_THEMES = "Themes"
TAB_OPENINGS = "Openings"

FILTER_TABS = (TAB_DIFFICULTY, TAB_QUALITY, TAB_THEMES, TAB_OPENINGS)


@dataclass(frozen=True, slots=True)
class NumericFilter:
    """One bounded integer the user can set with a slider.

    ``field`` is the attribute name shared by the settings and criteria
    dataclasses. ``default`` must leave the filter *open*: a fresh install,
    and every caller that does not set it (the arena refill builds criteria
    directly), has to behave as though the filter were absent.
    """

    field: str
    label: str
    minimum: int
    maximum: int
    default: int
    tab: str
    hint: str = ""


NUMERIC_FILTERS: tuple[NumericFilter, ...] = (
    NumericFilter("rating_min", "Rating min", 0, 3000, 800, TAB_DIFFICULTY),
    NumericFilter("rating_max", "Rating max", 0, 3000, 1200, TAB_DIFFICULTY),
    NumericFilter(
        "moves_min", "Your moves min", 1, 13, 1, TAB_DIFFICULTY,
        "How many moves you play; 1 is a one-move puzzle.",
    ),
    NumericFilter("moves_max", "Your moves max", 1, 13, 13, TAB_DIFFICULTY),
    NumericFilter(
        "popularity_min", "Popularity min", 0, 100, 80, TAB_QUALITY,
        "Lichess's up/down vote score for the puzzle.",
    ),
    NumericFilter(
        "rating_deviation_max", "Rating deviation max", 0, 500, 500, TAB_QUALITY,
        "Lower means the rating has settled; the median puzzle is 79.",
    ),
    NumericFilter(
        "nb_plays_min", "Times played min", 0, 100_000, 0, TAB_QUALITY,
        "Filters out barely-attempted puzzles; the median puzzle has 385.",
    ),
)


def filters_for(tab: str) -> tuple[NumericFilter, ...]:
    return tuple(item for item in NUMERIC_FILTERS if item.tab == tab)

