import pytest

from tetris.board import Board
from tetris.pieces import PieceKind


def test_dimensions_include_hidden_rows(empty_board: Board) -> None:
    assert empty_board.width == 10
    assert empty_board.height == 22
    assert empty_board.is_empty()


def test_walls_and_floor_are_blocked(empty_board: Board) -> None:
    assert empty_board.is_blocked(-1, 5)
    assert empty_board.is_blocked(10, 5)
    assert empty_board.is_blocked(3, 22)
    assert empty_board.is_blocked(3, -1)
    assert not empty_board.is_blocked(0, 0)


def test_from_rows_aligns_to_the_bottom() -> None:
    board = Board.from_rows(["T.........", "##########"])
    assert board.grid[20][0] is PieceKind.T
    assert board.grid[21][9] is PieceKind.O
    assert board.grid[19] == [None] * 10


def test_from_rows_rejects_wrong_width() -> None:
    with pytest.raises(ValueError):
        Board.from_rows(["###"])


def test_full_rows_and_clearing_shift_the_stack_down() -> None:
    board = Board.from_rows(
        [
            "#.........",
            "##########",
            "..#.......",
            "##########",
        ]
    )
    assert board.full_rows() == [19, 21]
    assert board.clear_rows(board.full_rows()) == 2
    assert board.grid[21][2] is not None
    assert board.grid[20][0] is not None
    assert board.full_rows() == []
    assert sum(cell is not None for row in board.grid for cell in row) == 2


def test_place_writes_cells_and_rejects_out_of_bounds(empty_board: Board) -> None:
    empty_board.place([(0, 21), (1, 21)], PieceKind.S)
    assert empty_board.grid[21][:2] == [PieceKind.S, PieceKind.S]
    assert not empty_board.fits([(0, 21)])
    with pytest.raises(ValueError):
        empty_board.place([(10, 0)], PieceKind.S)


def test_copy_is_independent(empty_board: Board) -> None:
    clone = empty_board.copy()
    clone.place([(0, 0)], PieceKind.I)
    assert empty_board.is_empty()


def test_heights_and_holes() -> None:
    board = Board.from_rows(
        [
            "#.........",
            "..........",
            "#.#.......",
        ]
    )
    assert board.column_heights()[:3] == [3, 0, 1]
    assert board.count_holes() == 1
