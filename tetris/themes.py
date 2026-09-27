"""Colour themes. Plain data, so adding a theme means adding one entry here."""

from __future__ import annotations

from dataclasses import dataclass

from tetris.pieces import PieceKind

RGB = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class Theme:
    name: str
    background: RGB
    well: RGB
    grid: RGB
    panel: RGB
    border: RGB
    text: RGB
    muted: RGB
    accent: RGB
    pieces: dict[PieceKind, RGB]

    def colour(self, kind: PieceKind) -> RGB:
        return self.pieces[kind]


_K = PieceKind

THEMES: tuple[Theme, ...] = (
    Theme(
        name="Midnight",
        background=(14, 16, 26),
        well=(20, 23, 36),
        grid=(32, 36, 54),
        panel=(24, 27, 42),
        border=(58, 64, 92),
        text=(228, 232, 245),
        muted=(128, 136, 168),
        accent=(255, 196, 64),
        pieces={
            _K.I: (64, 208, 232),
            _K.O: (244, 208, 64),
            _K.T: (168, 88, 224),
            _K.S: (96, 200, 96),
            _K.Z: (232, 80, 88),
            _K.J: (72, 112, 232),
            _K.L: (240, 144, 56),
        },
    ),
    Theme(
        name="Pastel",
        background=(246, 241, 235),
        well=(255, 252, 248),
        grid=(234, 226, 218),
        panel=(238, 231, 223),
        border=(205, 192, 180),
        text=(70, 60, 72),
        muted=(150, 136, 140),
        accent=(222, 110, 132),
        pieces={
            _K.I: (138, 208, 222),
            _K.O: (246, 214, 128),
            _K.T: (190, 160, 222),
            _K.S: (158, 212, 156),
            _K.Z: (238, 150, 150),
            _K.J: (140, 164, 226),
            _K.L: (244, 182, 132),
        },
    ),
    Theme(
        name="Handheld",
        background=(202, 220, 159),
        well=(155, 188, 15),
        grid=(139, 172, 15),
        panel=(175, 200, 90),
        border=(48, 98, 48),
        text=(15, 56, 15),
        muted=(48, 98, 48),
        accent=(15, 56, 15),
        pieces={kind: (15, 56, 15) if kind in (_K.I, _K.O, _K.S, _K.J) else (48, 98, 48) for kind in PieceKind},
    ),
    Theme(
        name="Neon",
        background=(6, 4, 14),
        well=(10, 8, 22),
        grid=(26, 20, 48),
        panel=(16, 12, 32),
        border=(90, 40, 160),
        text=(240, 236, 255),
        muted=(140, 120, 190),
        accent=(0, 255, 200),
        pieces={
            _K.I: (0, 240, 255),
            _K.O: (255, 240, 0),
            _K.T: (220, 0, 255),
            _K.S: (0, 255, 110),
            _K.Z: (255, 30, 90),
            _K.J: (40, 110, 255),
            _K.L: (255, 130, 0),
        },
    ),
)


def theme_names() -> list[str]:
    return [theme.name for theme in THEMES]


def theme_by_name(name: str) -> Theme:
    """Look a theme up case-insensitively."""
    for theme in THEMES:
        if theme.name.lower() == name.lower():
            return theme
    raise KeyError(f"unknown theme {name!r}; choose from {', '.join(theme_names())}")


def next_theme(current: Theme) -> Theme:
    index = THEMES.index(current)
    return THEMES[(index + 1) % len(THEMES)]
