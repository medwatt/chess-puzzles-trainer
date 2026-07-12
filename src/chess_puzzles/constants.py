"""Tunable constants: animations, engine timing, layout, and window sizes.

Edit values here to change behaviour across the app. Per-theme visual
defaults and things like database schema versions live in the modules
that own them, not here.
"""

from __future__ import annotations


# Board animations
MOVE_ANIMATION_MS: int = 180
MOVE_ANIMATION_TICK_MS: int = 16
FLASH_DURATION_MS: int = 500
FLASH_DEFAULT_COLOR: str = "#cc3333"
FLASH_CORRECT_COLOR: str = "#2f8f46"


# Engine timing
COMPUTER_REPLY_DELAY_MS: int = 350
# Refutation playback is a lesson, not a reply: each move needs to register
# before the next lands, so it paces slower than ordinary computer replies.
REFUTATION_STEP_DELAY_MS: int = 900
# The prefix recap replays moves the user already knows from the previous
# line, so it paces between a reply and a lesson: quick enough to feel like
# momentum, slow enough to follow.
PREFIX_RECAP_STEP_DELAY_MS: int = 450
ENGINE_POLL_INTERVAL_MS: int = 150
# Pause after solving so the result has time to register.
AUTO_NEXT_DELAY_MS: int = 1200


# Evaluation bar / scoring
EVALUATION_BAR_WIDTH: int = 34
EVALUATION_BAR_GAP: int = 6
EVALUATION_BAR_LABEL_FONT_SIZE: int = 9
EVALUATION_BAR_LABEL_BAND_HEIGHT: int = 22
EVAL_BAR_CLAMP_CP: int = 1000
MATE_BAR_CP: int = 1200


# Window geometry (Tk geometry strings or (w, h) tuples)
MAIN_WINDOW_MINSIZE: tuple[int, int] = (900, 620)
PGN_VIEWER_GEOMETRY: str = "1180x640"
PGN_VIEWER_MINSIZE: tuple[int, int] = (860, 520)
PLAY_WINDOW_GEOMETRY: str = "860x860"
PLAY_WINDOW_MINSIZE: tuple[int, int] = (860, 860)
# Wider than tall: the board shares the width with the sidebar, so a near-square
# board cell needs the window short enough to not leave vertical dead space.
VISION_WINDOW_GEOMETRY: str = "880x660"
VISION_WINDOW_MINSIZE: tuple[int, int] = (740, 560)
ENGINE_CONFIG_DIALOG_GEOMETRY: str = "760x420"
FONT_DIALOG_GEOMETRY: str = "460x420"
DATABASE_MANAGER_GEOMETRY: str = "980x600"


# App defaults
DEFAULT_UI_THEME_ID: str = "light"
DEFAULT_BOARD_THEME_ID: str = "lightwood3"
DEFAULT_PIECE_THEME_ID: str = "Cburnett"
