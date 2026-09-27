from tetris.board import Board
from tetris.mechanics import (
    TSpin,
    detect_tspin,
    drop_distance,
    is_grounded,
    spawn_position,
    try_rotate,
    try_shift,
)
from tetris.pieces import Piece, PieceKind


def test_spawn_positions_are_centred_left_biased(empty_board: Board) -> None:
    columns = {kind: sorted({x for x, _ in spawn_position(kind, empty_board).cells()}) for kind in PieceKind}
    assert columns[PieceKind.I] == [3, 4, 5, 6]
    assert columns[PieceKind.O] == [4, 5]
    for kind in (PieceKind.T, PieceKind.S, PieceKind.Z, PieceKind.J, PieceKind.L):
        assert columns[kind] == [3, 4, 5]


def test_shift_is_blocked_by_walls(empty_board: Board) -> None:
    piece = Piece(PieceKind.O, 0, 5)
    assert try_shift(empty_board, piece, -1, 0) is None
    assert try_shift(empty_board, piece, 1, 0) == Piece(PieceKind.O, 1, 5)


def test_drop_distance_and_grounding() -> None:
    board = Board.from_rows(["####......"])
    piece = Piece(PieceKind.O, 0, 0)
    assert drop_distance(board, piece) == 19
    landed = piece.shifted(0, 19)
    assert is_grounded(board, landed)
    assert not is_grounded(board, piece)


def test_rotation_without_obstruction_uses_first_test(empty_board: Board) -> None:
    result = try_rotate(empty_board, Piece(PieceKind.T, 4, 10), 1)
    assert result is not None
    assert result.kick_index == 0
    assert result.piece == Piece(PieceKind.T, 4, 10, 1)


def test_i_piece_kicks_off_the_right_wall(empty_board: Board) -> None:
    # Vertical I hugging the right wall (box column 2 == board column 9).
    vertical = Piece(PieceKind.I, 7, 10, 1)
    assert {x for x, _ in vertical.cells()} == {9}
    result = try_rotate(empty_board, vertical, 1)
    assert result is not None
    assert result.kick_index == 1
    assert sorted(x for x, _ in result.piece.cells()) == [6, 7, 8, 9]


def test_t_piece_kicks_off_the_left_wall(empty_board: Board) -> None:
    # T pointing right with its stem in column 0; rotating to "down" needs column -1.
    piece = Piece(PieceKind.T, -1, 10, 1)
    assert min(x for x, _ in piece.cells()) == 0
    result = try_rotate(empty_board, piece, 1)
    assert result is not None
    assert result.kick_index == 1
    assert min(x for x, _ in result.piece.cells()) == 0


def test_floor_kick_lifts_the_piece() -> None:
    board = Board.from_rows(["##########"] * 2)
    # Flat I resting on the stack; rotating to vertical must push it up.
    flat = Piece(PieceKind.I, 3, 18, 0)
    assert board.fits(flat.cells()) and is_grounded(board, flat)
    result = try_rotate(board, flat, 1)
    assert result is not None
    assert result.kick_index > 0
    assert max(y for _, y in result.piece.cells()) <= 19


def test_rotation_fails_when_every_test_collides() -> None:
    board = Board.from_rows(["#.########"] * 4)
    vertical_i = Piece(PieceKind.I, -1, 18, 1)
    assert board.fits(vertical_i.cells())
    assert try_rotate(board, vertical_i, 1) is None


TSD_ROWS = [
    "...#......",
    "#...######",
    "##.#######",
]


def test_full_tspin_detected_with_three_corners_and_both_front_corners() -> None:
    board = Board.from_rows(TSD_ROWS)
    piece = Piece(PieceKind.T, 1, 19, 2)
    assert board.fits(piece.cells())
    assert detect_tspin(board, piece, last_kick=0) is TSpin.FULL


def test_tspin_requires_rotation_as_last_move() -> None:
    board = Board.from_rows(TSD_ROWS)
    assert detect_tspin(board, Piece(PieceKind.T, 1, 19, 2), last_kick=None) is TSpin.NONE


def test_only_t_pieces_spin() -> None:
    board = Board.from_rows(TSD_ROWS)
    assert detect_tspin(board, Piece(PieceKind.L, 1, 19, 2), last_kick=0) is TSpin.NONE


def test_mini_tspin_when_front_corner_is_open() -> None:
    # T pointing up on the floor: the floor supplies both back corners, one front corner is filled.
    board = Board.from_rows(["#.........", ".........."])
    piece = Piece(PieceKind.T, 0, 20, 0)
    assert board.fits(piece.cells())
    assert detect_tspin(board, piece, last_kick=0) is TSpin.MINI
    # The long fifth kick upgrades a mini to a full T-spin.
    assert detect_tspin(board, piece, last_kick=4) is TSpin.FULL


def test_two_corners_is_not_a_tspin(empty_board: Board) -> None:
    piece = Piece(PieceKind.T, 4, 20, 0)
    assert detect_tspin(empty_board, piece, last_kick=0) is TSpin.NONE
