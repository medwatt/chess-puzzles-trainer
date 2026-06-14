from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from chess_puzzles.board.board_theme import BoardTheme, PieceTheme, default_board_theme, default_piece_theme
from chess_puzzles.platform.paths import assets_dir


@dataclass(frozen=True, slots=True)
class UiTheme:
    id: str
    name: str
    window_bg: str
    panel_bg: str
    sunken_bg: str
    text: str
    muted_text: str
    accent: str
    border: str
    button_bg: str
    button_active: str
    field_bg: str
    field_text: str
    menu_bg: str
    menu_active_bg: str
    menu_active_text: str


def built_in_ui_themes() -> dict[str, UiTheme]:
    light = UiTheme(
        id="light",
        name="Light",
        window_bg="#f4f5f7",
        panel_bg="#ffffff",
        sunken_bg="#eef1f4",
        text="#1f2328",
        muted_text="#636c76",
        accent="#0969da",
        border="#d0d7de",
        button_bg="#f6f8fa",
        button_active="#eaeef2",
        field_bg="#ffffff",
        field_text="#1f2328",
        menu_bg="#ffffff",
        menu_active_bg="#0969da",
        menu_active_text="#ffffff",
    )
    graphite_light = UiTheme(
        id="graphite_light",
        name="Graphite Light",
        window_bg="#f2f2f0",
        panel_bg="#ffffff",
        sunken_bg="#e4e4e1",
        text="#171717",
        muted_text="#5f6368",
        accent="#0f766e",
        border="#c6c6c2",
        button_bg="#eeeeeb",
        button_active="#dfdfdb",
        field_bg="#ffffff",
        field_text="#171717",
        menu_bg="#ffffff",
        menu_active_bg="#0f766e",
        menu_active_text="#ffffff",
    )
    dark = UiTheme(
        id="dark",
        name="Dark",
        window_bg="#202124",
        panel_bg="#2b2d31",
        sunken_bg="#17181b",
        text="#f2f3f5",
        muted_text="#b7bbc2",
        accent="#7aa2f7",
        border="#454852",
        button_bg="#363941",
        button_active="#464a55",
        field_bg="#24262b",
        field_text="#f2f3f5",
        menu_bg="#2b2d31",
        menu_active_bg="#4b6fbf",
        menu_active_text="#ffffff",
    )
    stone = UiTheme(
        id="stone",
        name="Stone",
        window_bg="#dcdad5",
        panel_bg="#e8e6e1",
        sunken_bg="#cbc8c2",
        text="#000000",
        muted_text="#6b6560",
        accent="#4a6882",
        border="#bab5ab",
        button_bg="#d0cdc7",
        button_active="#c2bfb8",
        field_bg="#e8e6e1",
        field_text="#2c2a27",
        menu_bg="#dcdad5",
        menu_active_bg="#4a6882",
        menu_active_text="#ffffff",
    )
    solarized = UiTheme(
        id="solarized",
        name="Solarized",
        window_bg="#fdf6e3",
        panel_bg="#eee8d5",
        sunken_bg="#f4ecd0",
        text="#586e75",
        muted_text="#93a1a1",
        accent="#268bd2",
        border="#d8d2c0",
        button_bg="#eee8d5",
        button_active="#e0dac6",
        field_bg="#fdf6e3",
        field_text="#586e75",
        menu_bg="#eee8d5",
        menu_active_bg="#268bd2",
        menu_active_text="#fdf6e3",
    )
    nord = UiTheme(
        id="nord",
        name="Nord",
        window_bg="#2e3440",
        panel_bg="#3b4252",
        sunken_bg="#232831",
        text="#eceff4",
        muted_text="#d8dee9",
        accent="#88c0d0",
        border="#4c566a",
        button_bg="#434c5e",
        button_active="#4c566a",
        field_bg="#3b4252",
        field_text="#eceff4",
        menu_bg="#3b4252",
        menu_active_bg="#5e81ac",
        menu_active_text="#eceff4",
    )
    gruvbox = UiTheme(
        id="gruvbox",
        name="Gruvbox",
        window_bg="#282828",
        panel_bg="#3c3836",
        sunken_bg="#1d2021",
        text="#ebdbb2",
        muted_text="#bdae93",
        accent="#fabd2f",
        border="#504945",
        button_bg="#3c3836",
        button_active="#504945",
        field_bg="#32302f",
        field_text="#ebdbb2",
        menu_bg="#3c3836",
        menu_active_bg="#d65d0e",
        menu_active_text="#fbf1c7",
    )
    dracula = UiTheme(
        id="dracula",
        name="Dracula",
        window_bg="#282a36",
        panel_bg="#343746",
        sunken_bg="#21222c",
        text="#f8f8f2",
        muted_text="#6272a4",
        accent="#bd93f9",
        border="#44475a",
        button_bg="#44475a",
        button_active="#565a72",
        field_bg="#343746",
        field_text="#f8f8f2",
        menu_bg="#44475a",
        menu_active_bg="#6272a4",
        menu_active_text="#f8f8f2",
    )
    monokai = UiTheme(
        id="monokai",
        name="Monokai",
        window_bg="#272822",
        panel_bg="#3e3d32",
        sunken_bg="#1e1f1c",
        text="#f8f8f2",
        muted_text="#75715e",
        accent="#66d9ef",
        border="#49483e",
        button_bg="#3e3d32",
        button_active="#49483e",
        field_bg="#383830",
        field_text="#f8f8f2",
        menu_bg="#3e3d32",
        menu_active_bg="#66d9ef",
        menu_active_text="#272822",
    )
    catppuccin_mocha = UiTheme(
        id="catppuccin_mocha",
        name="Catppuccin Mocha",
        window_bg="#1e1e2e",
        panel_bg="#313244",
        sunken_bg="#181825",
        text="#cdd6f4",
        muted_text="#a6adc8",
        accent="#cba6f7",
        border="#45475a",
        button_bg="#313244",
        button_active="#45475a",
        field_bg="#181825",
        field_text="#cdd6f4",
        menu_bg="#313244",
        menu_active_bg="#cba6f7",
        menu_active_text="#1e1e2e",
    )
    return {
        theme.id: theme
        for theme in (
            light,
            graphite_light,
            stone,
            solarized,
            dark,
            nord,
            gruvbox,
            dracula,
            monokai,
            catppuccin_mocha,
        )
    }


def built_in_board_themes() -> dict[str, BoardTheme]:
    board_root = assets_dir() / "img" / "boards"
    lightwood3 = BoardTheme(
        id="lightwood3",
        name="Lightwood3",
        light_square="#f0d9b5",
        dark_square="#b58863",
        selected_square="#f7ec6e",
        legal_target="#5f4629",
        coordinate_light="#b58863",
        coordinate_dark="#f0d9b5",
        texture_light=board_root / "LightWood3-l.gif",
        texture_dark=board_root / "LightWood3-d.gif",
    )
    lichess_brown = default_board_theme()
    lichess_brown = BoardTheme(
        id="lichess_brown",
        name="Lichess Brown",
        light_square=lichess_brown.light_square,
        dark_square=lichess_brown.dark_square,
        selected_square="#f7ec6e",
        legal_target="#646f40",
        coordinate_light="#b58863",
        coordinate_dark="#f0d9b5",
    )
    lichess_blue = BoardTheme(
        id="lichess_blue",
        name="Lichess Blue",
        light_square="#dee3e6",
        dark_square="#8ca2ad",
        selected_square="#f7ec6e",
        legal_target="#4f6977",
        coordinate_light="#8ca2ad",
        coordinate_dark="#dee3e6",
    )
    lichess_green = BoardTheme(
        id="lichess_green",
        name="Lichess Green",
        light_square="#ffffdd",
        dark_square="#86a666",
        selected_square="#f7ec6e",
        legal_target="#56723d",
        coordinate_light="#86a666",
        coordinate_dark="#ffffdd",
    )
    return {
        theme.id: theme
        for theme in (
            lightwood3,
            lichess_brown,
            lichess_blue,
            lichess_green,
        )
    }


def built_in_piece_themes() -> dict[str, PieceTheme]:
    image_root = assets_dir() / "img" / "pieces"
    merida_svg = assets_dir() / "svg" / "pieces" / "Merida"
    themes: list[PieceTheme] = []
    if image_root.exists():
        for directory in _piece_set_directories(image_root):
            svg_directory = merida_svg if directory.name == "Merida" and merida_svg.exists() else None
            themes.append(
                PieceTheme(
                    id=directory.name,
                    name=directory.name,
                    image_directory=directory,
                    svg_directory=svg_directory,
                )
            )
    elif merida_svg.exists():
        themes.append(PieceTheme(id="Merida", name="Merida", svg_directory=merida_svg))
    if not themes:
        themes.append(default_piece_theme())
    return {theme.id: theme for theme in themes}


def available_piece_themes(user_directory: str | Path | None = None) -> dict[str, PieceTheme]:
    """Bundled piece themes plus any discovered in the user's pieces folder.

    The user folder uses the same layout as assets/img/pieces: one
    subdirectory per set containing sprite sheets named <set>_<size>.
    If the user has a folder with the same name as a bundled set, it
    replaces the bundled raster art. Bundled SVG assets are kept in
    that case since user folders are raster-only.
    """
    themes = built_in_piece_themes()
    if not user_directory:
        return themes
    root = Path(user_directory).expanduser()
    if not root.is_dir():
        return themes
    for directory in _piece_set_directories(root):
        replaced = themes.get(directory.name)
        themes[directory.name] = PieceTheme(
            id=directory.name,
            name=directory.name,
            image_directory=directory,
            svg_directory=replaced.svg_directory if replaced is not None else None,
        )
    return themes


def _piece_set_directories(root: Path) -> list[Path]:
    return sorted(path for path in root.iterdir() if path.is_dir())
