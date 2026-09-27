"""Pure movement rules: spawning, shifting, SRS rotation and T-spin detection.

These functions never mutate their inputs, which lets the game, the tests and
the autoplayer all share exactly the same rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from tetris.board import Board
from tetris.pieces import BOX_SIZE, Piece, PieceKind, kick_offsets


class TSpin(Enum):
    """Result of the three-corner T-spin check."""

    NONE = "none"
    MINI = "mini"
    FULL = "full"


@dataclass(frozen=True, slots=True)
class Rotation:
    """A successful rotation and which kick test (0-4) made it fit."""

    piece: Piece
    kick_index: int


def spawn_position(kind: PieceKind, board: Board) -> Piece:
    """Where a new piece appears: centred (rounding left) with its box at the top of the grid."""
    x = (board.width - BOX_SIZE[kind]) // 2
    return Piece(kind, x, 0, 0)


def try_shift(board: Board, piece: Piece, dx: int, dy: int) -> Piece | None:
    """Return the piece moved by ``(dx, dy)``, or ``None`` if it would collide."""
    moved = piece.shifted(dx, dy)
    return moved if board.fits(moved.cells()) else None


def try_rotate(board: Board, piece: Piece, direction: int) -> Rotation | None:
    """Rotate using the SRS kick tests, returning the first position that fits."""
    target = piece.rotated(direction)
    for index, (dx, dy) in enumerate(kick_offsets(piece.kind, piece.rotation, target.rotation)):
        candidate = target.shifted(dx, dy)
        if board.fits(candidate.cells()):
            return Rotation(candidate, index)
    return None


def drop_distance(board: Board, piece: Piece) -> int:
    """How many rows the piece can fall before it lands (0 if it does not currently fit)."""
    cells = piece.cells()
    if not board.fits(cells):
        return 0
    # Scan each column below the piece directly instead of re-testing the whole
    # piece row by row; the autoplayer calls this thousands of times per plan.
    grid, height = board.grid, board.height
    distance = height
    for x, y in cells:
        below = y + 1
        while below < height and grid[below][x] is None:
            below += 1
        distance = min(distance, below - 1 - y)
    return distance


def is_grounded(board: Board, piece: Piece) -> bool:
    """True if the piece is resting on the stack or the floor."""
    return not board.fits(piece.shifted(0, 1).cells())


# Diagonal corners of the T's 3x3 box, and which two sit on the side the T
# points towards for each rotation state (0 = up, 1 = right, 2 = down, 3 = left).
_T_CORNERS = ((0, 0), (2, 0), (0, 2), (2, 2))
_T_FRONT_CORNERS = {
    0: ((0, 0), (2, 0)),
    1: ((2, 0), (2, 2)),
    2: ((0, 2), (2, 2)),
    3: ((0, 0), (0, 2)),
}
# SRS's fifth kick test is the long (1, 2) hop; guideline rules promote any
# T-spin reached through it to a full T-spin even if it would otherwise be mini.
_T_SPIN_TRIPLE_KICK = 4


def detect_tspin(board: Board, piece: Piece, last_kick: int | None) -> TSpin:
    """Classify a T piece about to lock using the three-corner rule.

    ``last_kick`` is the kick index of the rotation that was the piece's final
    move, or ``None`` if its final move was not a rotation (a T-spin requires
    the rotation to be the last thing that happened).
    """
    if piece.kind is not PieceKind.T or last_kick is None:
        return TSpin.NONE
    filled = {corner for corner in _T_CORNERS if board.is_blocked(piece.x + corner[0], piece.y + corner[1])}
    if len(filled) < 3:
        return TSpin.NONE
    front = _T_FRONT_CORNERS[piece.rotation]
    if all(corner in filled for corner in front) or last_kick == _T_SPIN_TRIPLE_KICK:
        return TSpin.FULL
    return TSpin.MINI
