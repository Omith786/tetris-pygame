"""The playfield grid: occupancy, collision and line clearing."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from tetris.pieces import Cell, PieceKind

WIDTH = 10
VISIBLE_HEIGHT = 20
# Rows above the visible field where pieces spawn. They are part of the grid so
# that a stack pushed into them is still represented correctly.
HIDDEN_ROWS = 2


class Board:
    """A rectangular grid of cells, each empty (``None``) or holding the kind that filled it."""

    def __init__(self, width: int = WIDTH, visible_height: int = VISIBLE_HEIGHT, hidden_rows: int = HIDDEN_ROWS) -> None:
        self.width = width
        self.visible_height = visible_height
        self.hidden_rows = hidden_rows
        self.height = visible_height + hidden_rows
        self.grid: list[list[PieceKind | None]] = [[None] * width for _ in range(self.height)]

    @classmethod
    def from_rows(cls, rows: Sequence[str], width: int = WIDTH, visible_height: int = VISIBLE_HEIGHT) -> Board:
        """Build a board from text rows aligned to the bottom of the field.

        ``.`` is empty. A piece letter (``IOTSZJL``) fills the cell with that
        kind; any other character, such as ``#``, fills it with an O cell.
        Mainly intended for tests and demos.
        """
        board = cls(width, visible_height)
        offset = board.height - len(rows)
        for row_index, text in enumerate(rows):
            if len(text) != width:
                raise ValueError(f"row {row_index} has width {len(text)}, expected {width}")
            for x, char in enumerate(text):
                if char != ".":
                    kind = PieceKind(char) if char in PieceKind.__members__ else PieceKind.O
                    board.grid[offset + row_index][x] = kind
        return board

    def copy(self) -> Board:
        """Return an independent copy (used by the autoplayer for look-ahead)."""
        clone = Board.__new__(Board)
        clone.width = self.width
        clone.visible_height = self.visible_height
        clone.hidden_rows = self.hidden_rows
        clone.height = self.height
        clone.grid = [row[:] for row in self.grid]
        return clone

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_blocked(self, x: int, y: int) -> bool:
        """True if the cell is outside the field or already filled."""
        return not self.in_bounds(x, y) or self.grid[y][x] is not None

    def fits(self, cells: Iterable[Cell]) -> bool:
        """True if every cell is inside the field and empty."""
        return not any(self.is_blocked(x, y) for x, y in cells)

    def place(self, cells: Iterable[Cell], kind: PieceKind) -> None:
        """Write a locked piece into the grid."""
        for x, y in cells:
            if not self.in_bounds(x, y):
                raise ValueError(f"cell {(x, y)} is outside the board")
            self.grid[y][x] = kind

    def full_rows(self) -> list[int]:
        """Indices of rows with no gaps, top to bottom."""
        return [y for y, row in enumerate(self.grid) if all(cell is not None for cell in row)]

    def clear_rows(self, rows: Iterable[int]) -> int:
        """Remove the given rows and let everything above fall. Returns the number removed."""
        doomed = set(rows)
        if not doomed:
            return 0
        kept = [row for y, row in enumerate(self.grid) if y not in doomed]
        fresh = [[None] * self.width for _ in doomed]
        self.grid = fresh + kept
        return len(doomed)

    def is_empty(self) -> bool:
        return all(cell is None for row in self.grid for cell in row)

    def column_heights(self) -> list[int]:
        """Height of the highest filled cell in each column (0 for an empty column)."""
        heights = []
        for x in range(self.width):
            height = 0
            for y in range(self.height):
                if self.grid[y][x] is not None:
                    height = self.height - y
                    break
            heights.append(height)
        return heights

    def count_holes(self) -> int:
        """Empty cells that have at least one filled cell somewhere above them."""
        holes = 0
        for x in range(self.width):
            covered = False
            for y in range(self.height):
                if self.grid[y][x] is not None:
                    covered = True
                elif covered:
                    holes += 1
        return holes
