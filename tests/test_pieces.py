from tetris.pieces import (
    ALL_KINDS,
    I_KICKS,
    JLSTZ_KICKS,
    ROTATIONS,
    Piece,
    PieceKind,
    kick_offsets,
)


def test_every_rotation_state_has_four_cells() -> None:
    for kind in ALL_KINDS:
        assert len(ROTATIONS[kind]) == 4
        for state in ROTATIONS[kind]:
            assert len(set(state)) == 4


def test_t_piece_states_match_srs() -> None:
    t = ROTATIONS[PieceKind.T]
    assert set(t[0]) == {(1, 0), (0, 1), (1, 1), (2, 1)}  # points up
    assert set(t[1]) == {(1, 0), (1, 1), (2, 1), (1, 2)}  # points right
    assert set(t[2]) == {(0, 1), (1, 1), (2, 1), (1, 2)}  # points down
    assert set(t[3]) == {(1, 0), (0, 1), (1, 1), (1, 2)}  # points left


def test_i_piece_rotates_within_its_4x4_box() -> None:
    i = ROTATIONS[PieceKind.I]
    assert set(i[0]) == {(0, 1), (1, 1), (2, 1), (3, 1)}
    assert set(i[1]) == {(2, 0), (2, 1), (2, 2), (2, 3)}
    assert set(i[2]) == {(0, 2), (1, 2), (2, 2), (3, 2)}
    assert set(i[3]) == {(1, 0), (1, 1), (1, 2), (1, 3)}


def test_o_piece_does_not_change_when_rotated() -> None:
    states = ROTATIONS[PieceKind.O]
    assert all(set(state) == set(states[0]) for state in states)
    assert kick_offsets(PieceKind.O, 0, 1) == ((0, 0),)


def test_kick_tables_are_antisymmetric() -> None:
    # In SRS, undoing a rotation tries exactly the negated offsets.
    for table in (JLSTZ_KICKS, I_KICKS):
        for (a, b), offsets in table.items():
            reverse = table[(b, a)]
            assert reverse == tuple((-dx, -dy) for dx, dy in offsets)


def test_kicks_are_converted_to_screen_coordinates() -> None:
    # Reference (y-up) JLSTZ 0->R third test is (-1, +1): left one and UP one.
    assert kick_offsets(PieceKind.T, 0, 1)[2] == (-1, -1)
    assert kick_offsets(PieceKind.I, 0, 1)[4] == (1, -2)


def test_piece_helpers_return_new_objects() -> None:
    piece = Piece(PieceKind.T, 3, 5)
    assert piece.shifted(1, 2) == Piece(PieceKind.T, 4, 7, 0)
    assert piece.rotated(-1).rotation == 3
    assert piece.rotated(1).rotated(1).rotated(1).rotated(1) == piece
    assert set(piece.cells()) == {(4, 5), (3, 6), (4, 6), (5, 6)}
