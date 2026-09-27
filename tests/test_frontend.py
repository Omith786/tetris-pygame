"""Headless checks of the pygame layer: rendering every screen and driving the app with synthetic keys."""

from __future__ import annotations

from pathlib import Path

import pygame
import pytest

from tests.conftest import make_game
from tetris.app import App, build_parser
from tetris.effects import Effects
from tetris.game import Phase
from tetris.highscore import HighScoreTable, ScoreEntry
from tetris.render import BOARD_LEFT, BOARD_TOP, CELL, WINDOW_SIZE, HudState, Renderer, Screen, blend
from tetris.themes import THEMES, next_theme, theme_by_name


@pytest.fixture
def surface() -> pygame.Surface:
    pygame.init()
    yield pygame.display.set_mode(WINDOW_SIZE)
    pygame.quit()


def test_blend() -> None:
    assert blend((0, 0, 0), (255, 255, 255), 0.5) == (128, 128, 128)
    assert blend((10, 20, 30), (0, 0, 0), 0) == (10, 20, 30)
    assert blend((10, 20, 30), (0, 0, 0), 5) == (0, 0, 0)


def test_theme_lookup_and_cycling() -> None:
    assert theme_by_name("neon").name == "Neon"
    assert next_theme(THEMES[-1]) is THEMES[0]
    with pytest.raises(KeyError):
        theme_by_name("sepia")


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.name)
@pytest.mark.parametrize("screen", list(Screen))
def test_every_screen_renders_in_every_theme(surface: pygame.Surface, theme, screen: Screen) -> None:
    game = make_game("TIO", rows=["####..####"], line_clear_delay=0.3)
    game.hold()
    renderer = Renderer(surface, theme)
    hud = HudState(screen=screen, high_scores=[ScoreEntry(1234, 12, 2, "2026-01-01")], final_rank=1)
    renderer.draw(game, Effects(), hud)
    # Top-left corner of the well is either empty well or grid, never the page background.
    assert surface.get_at((BOARD_LEFT + 2, BOARD_TOP + 2))[:3] != theme.background or screen is not Screen.PLAYING


def test_line_clear_and_pause_frames_render(surface: pygame.Surface) -> None:
    game = make_game("OT", rows=["####..####"], line_clear_delay=0.3)
    game.hard_drop()
    effects = Effects()
    effects.handle(game.drain_events())
    assert game.phase is Phase.CLEARING and effects.popups
    renderer = Renderer(surface, THEMES[0])
    renderer.draw(game, effects, HudState(screen=Screen.PLAYING))
    # The clearing row flashes towards white.
    x = BOARD_LEFT + CELL // 2
    y = BOARD_TOP + 19 * CELL + CELL // 2
    assert sum(surface.get_at((x, y))[:3]) > sum(THEMES[0].colour(game.board.grid[21][0])) + 60
    game.tick(0.5)
    game.toggle_pause()
    renderer.draw(game, effects, HudState(screen=Screen.PLAYING))


def _args(tmp_path: Path, *extra: str):
    return build_parser().parse_args(["--seed", "1", "--highscores", str(tmp_path / "scores.json"), *extra])


def _key(app: App, key: int, up: bool = False) -> None:
    app.handle_event(pygame.event.Event(pygame.KEYUP if up else pygame.KEYDOWN, key=key))


def test_app_flow_from_title_to_game_over(tmp_path: Path) -> None:
    app = App(_args(tmp_path))
    try:
        assert app.hud.screen is Screen.TITLE
        _key(app, pygame.K_RETURN)
        assert app.hud.screen is Screen.PLAYING
        start = app.game.active
        _key(app, pygame.K_LEFT)
        assert app.game.active is not None and start is not None
        assert app.game.active.x == start.x - 1
        _key(app, pygame.K_LEFT, up=True)
        _key(app, pygame.K_SPACE)
        assert app.game.stats.pieces == 1
        _key(app, pygame.K_p)
        assert app.game.paused
        _key(app, pygame.K_p)
        _key(app, pygame.K_t)
        assert app.renderer.theme is THEMES[1]

        # Top out quickly by hard dropping repeatedly, then check the score was saved.
        for _ in range(200):
            if app.hud.screen is Screen.GAME_OVER:
                break
            _key(app, pygame.K_SPACE)
            app.update(1 / 60)
        assert app.hud.screen is Screen.GAME_OVER
        assert app.hud.final_rank == 1
        saved = HighScoreTable.load(tmp_path / "scores.json")
        assert saved.best == app.game.score > 0
    finally:
        pygame.quit()


def test_autoplay_plays_but_is_not_recorded(tmp_path: Path) -> None:
    app = App(_args(tmp_path, "--autoplay"))
    try:
        assert app.hud.screen is Screen.PLAYING and app.hud.autoplay
        for _ in range(600):
            app.update(1 / 60)
        assert app.game.stats.pieces >= 10
        assert not app.game.is_over
        # Swap in a position that is already topped out to end the game immediately.
        app.game = make_game("OT", rows=[".#########"] * 22)
        app.update(1 / 60)
        assert app.hud.screen is Screen.GAME_OVER
        assert not app.hud.recorded
        assert not (tmp_path / "scores.json").exists()
    finally:
        pygame.quit()


def test_losing_focus_pauses(tmp_path: Path) -> None:
    app = App(_args(tmp_path))
    try:
        _key(app, pygame.K_RETURN)
        app.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
        assert app.game.paused
    finally:
        pygame.quit()


def test_main_loop_runs_headless(tmp_path: Path) -> None:
    app = App(_args(tmp_path, "--autoplay"))
    app.run(max_frames=30)
    assert app.game.stats.elapsed > 0
