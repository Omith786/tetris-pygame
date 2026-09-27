import pytest

from tests.conftest import make_game
from tetris.game import ClearEvent, Game, GameConfig, GameOverEvent, LevelUpEvent, LockEvent, Phase
from tetris.mechanics import TSpin, detect_tspin, drop_distance
from tetris.pieces import Piece, PieceKind


def test_new_game_spawns_first_piece_in_view() -> None:
    game = make_game("T")
    assert game.active is not None
    assert game.active.kind is PieceKind.T
    # Spawned in the hidden rows, then stepped down one row into view.
    assert game.active.y == 1
    assert max(y for _, y in game.active.cells()) >= game.board.hidden_rows
    assert game.spawn_id == 1


def test_next_queue_previews_upcoming_pieces() -> None:
    game = make_game("TIJLSZO")
    assert game.next_queue == [PieceKind.I, PieceKind.J, PieceKind.L, PieceKind.S, PieceKind.Z]
    game.hard_drop()
    assert game.active is not None and game.active.kind is PieceKind.I


def test_seeded_games_are_reproducible() -> None:
    a, b = Game(seed=11), Game(seed=11)
    assert a.next_queue == b.next_queue
    assert a.active == b.active


def test_invalid_config_is_rejected() -> None:
    with pytest.raises(ValueError):
        GameConfig(scoring="nonsense")
    with pytest.raises(ValueError):
        GameConfig(start_level=0)


def test_move_and_rotate_respect_walls() -> None:
    game = make_game("O")
    assert all(game.move(-1) for _ in range(4))
    assert not game.move(-1)
    assert game.rotate(1)  # the O "rotates" in place and always succeeds


def test_gravity_moves_one_row_per_second_at_level_one() -> None:
    game = make_game("T")
    assert game.active is not None
    start = game.active.y
    game.tick(0.99)
    assert game.active.y == start
    game.tick(0.02)
    assert game.active.y == start + 1


def test_higher_levels_fall_faster() -> None:
    game = make_game("T", start_level=10)
    assert game.active is not None
    start = game.active.y
    game.tick(1.0)
    assert game.active.y - start >= 10


def test_soft_drop_scores_one_point_per_row() -> None:
    game = make_game("T")
    assert game.active is not None
    start = game.active.y
    game.set_soft_drop(True)
    for _ in range(10):
        game.tick(0.051)
    fallen = game.active.y - start
    assert fallen == 10
    assert game.score == fallen


def test_pressing_soft_drop_does_not_spend_banked_gravity_instantly() -> None:
    game = make_game("T")
    assert game.active is not None
    game.tick(0.9)  # nearly a full normal gravity step banked
    start = game.active.y
    game.set_soft_drop(True)
    game.tick(0.001)
    assert game.active.y - start <= 1


def test_hard_drop_locks_and_scores_two_points_per_row() -> None:
    game = make_game("OT")
    assert game.active is not None
    distance = drop_distance(game.board, game.active)
    game.hard_drop()
    assert game.score == 2 * distance
    assert game.board.grid[21][4] is PieceKind.O
    assert game.active is not None and game.active.kind is PieceKind.T
    assert game.stats.pieces == 1
    events = game.drain_events()
    assert any(isinstance(e, LockEvent) for e in events)
    assert game.drain_events() == []


def test_ghost_marks_the_landing_position() -> None:
    game = make_game("I")
    assert game.ghost is not None and game.active is not None
    assert game.ghost == game.active.shifted(0, drop_distance(game.board, game.active))


def _ground(game: Game) -> None:
    assert game.active is not None
    game.active = game.active.shifted(0, drop_distance(game.board, game.active))


def test_lock_delay_gives_half_a_second_on_the_ground() -> None:
    game = make_game("OT")
    _ground(game)
    game.tick(0.45)
    assert game.stats.pieces == 0
    assert 0.8 < game.lock_progress < 1.0
    game.tick(0.1)
    assert game.stats.pieces == 1


def test_moving_on_the_ground_resets_lock_delay() -> None:
    game = make_game("OT")
    _ground(game)
    game.tick(0.4)
    assert game.move(1)
    game.tick(0.4)
    assert game.stats.pieces == 0
    game.tick(0.15)
    assert game.stats.pieces == 1


def test_lock_resets_are_capped() -> None:
    game = make_game("OT", max_lock_resets=2)
    _ground(game)
    for direction in (1, -1):
        game.tick(0.3)
        assert game.move(direction)
    game.tick(0.3)
    assert game.move(1)  # third move is allowed but no longer resets the timer
    game.tick(0.25)
    assert game.stats.pieces == 1


def test_hold_stores_then_swaps_once_per_piece() -> None:
    game = make_game("TIJ")
    assert game.hold()
    assert game.hold_kind is PieceKind.T
    assert game.active is not None and game.active.kind is PieceKind.I
    assert not game.hold()  # only one hold per piece
    game.hard_drop()
    assert game.can_hold
    assert game.active is not None and game.active.kind is PieceKind.J
    assert game.hold()
    assert game.hold_kind is PieceKind.J
    assert game.active is not None and game.active.kind is PieceKind.T


def test_single_line_clear() -> None:
    game = make_game("O", rows=["####..####"])
    game.hard_drop()
    assert game.lines == 1
    assert game.score == 100 + 2 * 19
    # The O's top half drops into the cleared row.
    assert game.board.grid[21][4:6] == [PieceKind.O, PieceKind.O]
    assert game.board.grid[20] == [None] * 10
    clear = next(e for e in game.drain_events() if isinstance(e, ClearEvent))
    assert clear.lines == 1 and clear.rows == (21,)


def test_line_clear_delay_holds_the_rows_before_collapsing() -> None:
    game = make_game("OT", rows=["####..####"], line_clear_delay=0.3)
    game.hard_drop()
    assert game.phase is Phase.CLEARING
    assert game.clearing_rows == (21,)
    assert game.active is None
    assert not game.move(1)
    game.tick(0.15)
    assert game.clear_progress == pytest.approx(0.5)
    game.tick(0.2)
    assert game.phase is Phase.PLAYING
    assert game.board.grid[21][4] is PieceKind.O
    assert game.active is not None and game.active.kind is PieceKind.T


def _drop_vertical_i_in_column_zero(game: Game) -> None:
    assert game.active is not None and game.active.kind is PieceKind.I
    assert game.rotate(1)
    while game.move(-1):
        pass
    game.hard_drop()


def test_back_to_back_tetrises_and_combo() -> None:
    game = make_game("II", rows=[".#########"] * 8)
    _drop_vertical_i_in_column_zero(game)
    _drop_vertical_i_in_column_zero(game)
    clears = [e for e in game.drain_events() if isinstance(e, ClearEvent)]
    assert [c.lines for c in clears] == [4, 4]
    assert [c.back_to_back for c in clears] == [False, True]
    assert [c.points for c in clears] == [800, 1200 + 50]
    assert game.lines == 8
    assert game.stats.tetrises == 2
    assert game.board.is_empty()


def test_combo_resets_after_a_lock_without_a_clear() -> None:
    game = make_game("OOO", rows=["####..####", "####..####"])
    game.hard_drop()
    assert game.combo == 0
    game.hard_drop()
    assert game.combo == -1


def test_tspin_double_is_scored() -> None:
    game = make_game("T", rows=["...#......", "#...######", "##.#######"])
    # Place the T pointing right just above the slot, then spin it in.
    game.active = Piece(PieceKind.T, 1, 19, 1)
    assert game.rotate(1)
    game.hard_drop()
    clear = next(e for e in game.drain_events() if isinstance(e, ClearEvent))
    assert clear.tspin is TSpin.FULL
    assert clear.lines == 2
    assert game.score == 1200
    assert game.stats.tspins == 1


def test_dropping_after_a_rotation_cancels_the_spin() -> None:
    # Column 2 and the cell under column 0 form a three-corner pocket a T can fall straight into.
    game = make_game("T", rows=["..#.......", "..#.......", "#.#......."])
    game.active = Piece(PieceKind.T, 0, 10, 0)
    assert game.rotate(-1)
    landed = game.ghost
    assert landed is not None
    assert detect_tspin(game.board, landed, last_kick=0) is TSpin.MINI  # would count if spun in
    game.hard_drop()
    assert game.stats.pieces == 1
    assert game.stats.tspins == 0
    assert not any(isinstance(e, ClearEvent) for e in game.drain_events())


def test_level_up_after_ten_lines() -> None:
    game = make_game("O", rows=["####..####"])
    game.lines = 9
    game.hard_drop()
    assert game.level == 2
    assert any(isinstance(e, LevelUpEvent) and e.level == 2 for e in game.drain_events())


def test_classic_scoring_rule() -> None:
    game = make_game("O", rows=["####..####"], scoring="classic")
    game.hard_drop()
    assert game.score == 40 + 19


def test_block_out_ends_the_game() -> None:
    game = make_game("OT", rows=[".#########"] * 22)
    assert game.is_over
    assert game.active is None
    assert any(isinstance(e, GameOverEvent) and e.reason == "block out" for e in game.drain_events())


def test_lock_out_ends_the_game() -> None:
    game = make_game("OT", rows=["#########."] * 20)
    assert game.active is not None and game.active.y == 0  # no room to step into view
    game.hard_drop()
    assert game.is_over
    assert any(isinstance(e, GameOverEvent) and e.reason == "lock out" for e in game.drain_events())
    game.tick(1.0)  # further ticks are harmless
    assert not game.move(1)


def test_pause_freezes_time_and_controls() -> None:
    game = make_game("T")
    assert game.active is not None
    start = game.active
    game.toggle_pause()
    game.tick(5.0)
    assert not game.move(1)
    assert not game.hold()
    game.hard_drop()
    assert game.active == start
    assert game.stats.elapsed == 0
    game.toggle_pause()
    game.tick(1.01)
    assert game.active.y == start.y + 1


def test_fall_progress_reports_partial_steps() -> None:
    game = make_game("T")
    game.tick(0.25)
    assert game.fall_progress == pytest.approx(0.25)
    _ground(game)
    assert game.fall_progress == 0.0
