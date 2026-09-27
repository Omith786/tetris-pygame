from tetris.ai import Action, AutoPlayer, best_placement, candidate_placements, evaluate
from tetris.board import Board
from tetris.game import Game, GameConfig
from tetris.mechanics import spawn_position
from tetris.pieces import PieceKind


def test_evaluate_penalises_holes() -> None:
    flat = Board.from_rows(["##########"[:4] + "......"])
    holey = Board.from_rows(["####......", "#.#......."])
    assert evaluate(flat, 0) > evaluate(holey, 0)


def test_candidates_cover_every_column_and_rotation(empty_board: Board) -> None:
    candidates = candidate_placements(empty_board, spawn_position(PieceKind.T, empty_board))
    # A T has 8 columns in its two flat states and 9 in its two upright ones.
    assert len(candidates) == 8 + 9 + 8 + 9
    assert all(c.actions[-1] is Action.DROP for c in candidates)


def test_prefers_the_tetris_well() -> None:
    board = Board.from_rows(["#########."] * 4)
    placement = best_placement(board, spawn_position(PieceKind.I, board))
    assert placement is not None
    assert {x for x, _ in placement.piece.cells()} == {9}


def test_autoplayer_survives_and_clears_lines() -> None:
    game = Game(GameConfig(line_clear_delay=0.0), seed=5)
    bot = AutoPlayer(game, action_interval=0.0)
    for _ in range(4000):
        if game.is_over or game.stats.pieces >= 150:
            break
        bot.update(1 / 60)
        game.tick(1 / 60)
    assert not game.is_over
    assert game.stats.pieces >= 150
    assert game.lines >= 50


def test_autoplayer_uses_hold_when_it_helps() -> None:
    # An S cannot fill this single-width well cleanly; the held I can.
    board = Board.from_rows(["#########."] * 4)
    game = Game(GameConfig(line_clear_delay=0.0), board=board)
    game.active = spawn_position(PieceKind.S, board)
    game.hold_kind = PieceKind.I
    bot = AutoPlayer(game)
    bot.plan()
    assert list(bot._queue) == [Action.HOLD]


def test_autoplayer_keeps_up_at_high_levels() -> None:
    game = Game(GameConfig(start_level=15, line_clear_delay=0.0), seed=2)
    bot = AutoPlayer(game)
    for _ in range(2000):
        if game.is_over or game.stats.pieces >= 80:
            break
        bot.update(1 / 60)
        game.tick(1 / 60)
    assert not game.is_over
    assert game.stats.pieces >= 80
