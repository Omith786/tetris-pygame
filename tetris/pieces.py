"""Tetromino shapes, rotation states and SRS wall-kick data.

Coordinates throughout the package use screen orientation: ``x`` grows to the
right and ``y`` grows downwards, so row 0 is the top of the board.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

Cell = tuple[int, int]


class PieceKind(StrEnum):
    """The seven standard tetrominoes."""

    I = "I"  # noqa: E741 - the canonical name of the piece
    O = "O"  # noqa: E741
    T = "T"
    S = "S"
    Z = "Z"
    J = "J"
    L = "L"


ALL_KINDS: tuple[PieceKind, ...] = tuple(PieceKind)

# Spawn orientation of each piece inside its bounding box. The box size matters:
# SRS rotates every piece about the centre of its box, which is why I uses a 4x4
# box and O a 2x2 one.
_SPAWN_SHAPES: dict[PieceKind, tuple[int, tuple[Cell, ...]]] = {
    PieceKind.I: (4, ((0, 1), (1, 1), (2, 1), (3, 1))),
    PieceKind.O: (2, ((0, 0), (1, 0), (0, 1), (1, 1))),
    PieceKind.T: (3, ((1, 0), (0, 1), (1, 1), (2, 1))),
    PieceKind.S: (3, ((1, 0), (2, 0), (0, 1), (1, 1))),
    PieceKind.Z: (3, ((0, 0), (1, 0), (1, 1), (2, 1))),
    PieceKind.J: (3, ((0, 0), (0, 1), (1, 1), (2, 1))),
    PieceKind.L: (3, ((2, 0), (0, 1), (1, 1), (2, 1))),
}


def _rotate_cw(cells: tuple[Cell, ...], size: int) -> tuple[Cell, ...]:
    return tuple(sorted((size - 1 - y, x) for x, y in cells))


def _build_rotations() -> dict[PieceKind, tuple[tuple[Cell, ...], ...]]:
    table: dict[PieceKind, tuple[tuple[Cell, ...], ...]] = {}
    for kind, (size, cells) in _SPAWN_SHAPES.items():
        states = [tuple(sorted(cells))]
        for _ in range(3):
            states.append(_rotate_cw(states[-1], size))
        table[kind] = tuple(states)
    return table


#: ``ROTATIONS[kind][r]`` lists the box-relative cells of ``kind`` in rotation
#: state ``r`` (0 = spawn, 1 = R, 2 = 180, 3 = L).
ROTATIONS = _build_rotations()

#: Bounding-box size per piece, used for spawning and T-spin corner checks.
BOX_SIZE: dict[PieceKind, int] = {kind: size for kind, (size, _) in _SPAWN_SHAPES.items()}

# Kick offsets exactly as published in the SRS reference, which uses y-up
# coordinates. Keeping the reference layout makes the table easy to audit; the
# conversion to y-down happens once in ``_to_screen``.
_JLSTZ_KICKS_YUP: dict[tuple[int, int], tuple[Cell, ...]] = {
    (0, 1): ((0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)),
    (1, 0): ((0, 0), (1, 0), (1, -1), (0, 2), (1, 2)),
    (1, 2): ((0, 0), (1, 0), (1, -1), (0, 2), (1, 2)),
    (2, 1): ((0, 0), (-1, 0), (-1, 1), (0, -2), (-1, -2)),
    (2, 3): ((0, 0), (1, 0), (1, 1), (0, -2), (1, -2)),
    (3, 2): ((0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)),
    (3, 0): ((0, 0), (-1, 0), (-1, -1), (0, 2), (-1, 2)),
    (0, 3): ((0, 0), (1, 0), (1, 1), (0, -2), (1, -2)),
}

_I_KICKS_YUP: dict[tuple[int, int], tuple[Cell, ...]] = {
    (0, 1): ((0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)),
    (1, 0): ((0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)),
    (1, 2): ((0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)),
    (2, 1): ((0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)),
    (2, 3): ((0, 0), (2, 0), (-1, 0), (2, 1), (-1, -2)),
    (3, 2): ((0, 0), (-2, 0), (1, 0), (-2, -1), (1, 2)),
    (3, 0): ((0, 0), (1, 0), (-2, 0), (1, -2), (-2, 1)),
    (0, 3): ((0, 0), (-1, 0), (2, 0), (-1, 2), (2, -1)),
}


def _to_screen(table: dict[tuple[int, int], tuple[Cell, ...]]) -> dict[tuple[int, int], tuple[Cell, ...]]:
    return {key: tuple((dx, -dy) for dx, dy in offsets) for key, offsets in table.items()}


JLSTZ_KICKS = _to_screen(_JLSTZ_KICKS_YUP)
I_KICKS = _to_screen(_I_KICKS_YUP)


def kick_offsets(kind: PieceKind, from_rotation: int, to_rotation: int) -> tuple[Cell, ...]:
    """Return the ordered (dx, dy) offsets SRS tries for a rotation, in y-down coordinates."""
    if kind is PieceKind.O:
        return ((0, 0),)
    table = I_KICKS if kind is PieceKind.I else JLSTZ_KICKS
    return table[(from_rotation % 4, to_rotation % 4)]


@dataclass(frozen=True, slots=True)
class Piece:
    """An immutable tetromino placed on the board.

    ``x`` and ``y`` locate the top-left corner of the piece's bounding box, so
    the occupied cells are the rotation template translated by that offset.
    """

    kind: PieceKind
    x: int
    y: int
    rotation: int = 0

    def cells(self) -> tuple[Cell, ...]:
        """Absolute board cells covered by the piece."""
        return tuple((self.x + cx, self.y + cy) for cx, cy in ROTATIONS[self.kind][self.rotation])

    def shifted(self, dx: int, dy: int) -> Piece:
        """Return a copy translated by ``(dx, dy)``."""
        return Piece(self.kind, self.x + dx, self.y + dy, self.rotation)

    def rotated(self, direction: int) -> Piece:
        """Return a copy rotated in place (no kicks); +1 is clockwise, -1 anticlockwise."""
        return Piece(self.kind, self.x, self.y, (self.rotation + direction) % 4)


def shape_cells(kind: PieceKind, rotation: int = 0) -> tuple[Cell, ...]:
    """Box-relative cells of a piece, handy for drawing previews."""
    return ROTATIONS[kind][rotation % 4]
