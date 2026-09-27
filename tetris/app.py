"""The pygame front end: window, event loop, key bindings and screen flow."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import pygame

from tetris.ai import AutoPlayer
from tetris.controls import LEFT, RIGHT, AutoShift
from tetris.effects import Effects
from tetris.game import Game, GameConfig
from tetris.highscore import DEFAULT_PATH, HighScoreTable, ScoreEntry
from tetris.render import WINDOW_SIZE, HudState, Renderer, Screen
from tetris.scoring import SCORING_RULES
from tetris.themes import next_theme, theme_by_name, theme_names

FPS = 60
# A long stall (window drag, breakpoint) should not fast-forward the game.
MAX_FRAME_TIME = 0.1

# Rebinding a control means editing one of these tuples.
KEYS_LEFT = (pygame.K_LEFT,)
KEYS_RIGHT = (pygame.K_RIGHT,)
KEYS_SOFT_DROP = (pygame.K_DOWN,)
KEYS_HARD_DROP = (pygame.K_SPACE,)
KEYS_ROTATE_CW = (pygame.K_UP, pygame.K_x)
KEYS_ROTATE_CCW = (pygame.K_z, pygame.K_LCTRL, pygame.K_RCTRL)
KEYS_HOLD = (pygame.K_c, pygame.K_LSHIFT, pygame.K_RSHIFT)
KEYS_PAUSE = (pygame.K_p, pygame.K_ESCAPE)
KEYS_CONFIRM = (pygame.K_RETURN, pygame.K_KP_ENTER)


class App:
    """Owns the window and wires input, the game, the autoplayer and the renderer together."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        pygame.init()
        pygame.display.set_caption("Tetris")
        self.surface = pygame.display.set_mode(WINDOW_SIZE)
        self.clock = pygame.time.Clock()
        self.renderer = Renderer(self.surface, theme_by_name(args.theme))
        self.scores = HighScoreTable.load(args.highscores)
        self.effects = Effects()
        self.shift = AutoShift(das=args.das / 1000, arr=args.arr / 1000)
        self.hud = HudState(
            high_scores=list(self.scores.entries),
            show_ghost=not args.no_ghost,
            smooth_fall=not args.no_smooth,
        )
        self.game = self._new_game()
        self.autoplayer = AutoPlayer(self.game)
        self.autoplay_used = False
        self.running = True
        if args.autoplay:
            self._set_autoplay(True)
            self._start()

    # ------------------------------------------------------------- lifecycle

    def _new_game(self) -> Game:
        config = GameConfig(start_level=self.args.level, scoring=self.args.scoring)
        return Game(config, seed=self.args.seed)

    def _start(self) -> None:
        self.game = self._new_game()
        self.autoplayer.reset(self.game)
        self.autoplay_used = False
        self.effects.clear()
        self.shift.clear()
        self.hud.screen = Screen.PLAYING
        self.hud.final_rank = None
        self.hud.recorded = True

    def _finish(self) -> None:
        """Record the result once the game has ended."""
        self.hud.screen = Screen.GAME_OVER
        self.hud.recorded = not self.autoplay_used
        if self.hud.recorded:
            entry = ScoreEntry.today(self.game.score, self.game.lines, self.game.level)
            self.hud.final_rank = self.scores.add(entry)
            if self.hud.final_rank is not None:
                self.scores.save()
                self.hud.high_scores = list(self.scores.entries)

    def _set_autoplay(self, enabled: bool) -> None:
        self.hud.autoplay = enabled
        if enabled:
            self.autoplayer.reset(self.game)
            self.game.set_soft_drop(False)
            self.shift.clear()

    # ------------------------------------------------------------------ loop

    def run(self, max_frames: int | None = None) -> None:
        frames = 0
        while self.running:
            dt = min(self.clock.tick(FPS) / 1000, MAX_FRAME_TIME)
            for event in pygame.event.get():
                self.handle_event(event)
            self.update(dt)
            self.renderer.draw(self.game, self.effects, self.hud)
            pygame.display.flip()
            frames += 1
            if max_frames is not None and frames >= max_frames:
                break
        pygame.quit()

    def update(self, dt: float) -> None:
        if self.hud.screen is not Screen.PLAYING:
            self.effects.update(dt)
            return
        if not self.game.paused:
            if self.hud.autoplay:
                # Any game the autoplayer touches is kept off the leaderboard.
                self.autoplay_used = True
                self.autoplayer.update(dt)
            else:
                steps = self.shift.update(dt)
                direction = 1 if steps > 0 else -1
                for _ in range(abs(steps)):
                    if not self.game.move(direction):
                        break
        self.game.tick(dt)
        self.effects.handle(self.game.drain_events())
        self.effects.update(dt)
        if self.game.is_over:
            self._finish()

    # ---------------------------------------------------------------- input

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.WINDOWFOCUSLOST:
            if self.hud.screen is Screen.PLAYING and not self.game.paused:
                self._toggle_pause()
        elif event.type == pygame.KEYDOWN:
            self._key_down(event.key)
        elif event.type == pygame.KEYUP:
            self._key_up(event.key)

    def _key_down(self, key: int) -> None:
        # Keys that work on every screen.
        if key == pygame.K_t:
            self.renderer.theme = next_theme(self.renderer.theme)
            return
        if key == pygame.K_g:
            self.hud.show_ghost = not self.hud.show_ghost
            return
        if key == pygame.K_a:
            self._set_autoplay(not self.hud.autoplay)
            return

        if self.hud.screen is not Screen.PLAYING:
            if key in KEYS_CONFIRM:
                self._start()
            elif key in (pygame.K_ESCAPE, pygame.K_q):
                self.running = False
            return

        game = self.game
        if key in KEYS_PAUSE:
            self._toggle_pause()
            return
        if game.paused:
            if key == pygame.K_r:
                self._start()
            elif key == pygame.K_q:
                self.running = False
            return
        if self.hud.autoplay:
            return

        if key in KEYS_LEFT:
            game.move(self.shift.press(LEFT))
        elif key in KEYS_RIGHT:
            game.move(self.shift.press(RIGHT))
        elif key in KEYS_SOFT_DROP:
            game.set_soft_drop(True)
        elif key in KEYS_HARD_DROP:
            game.hard_drop()
        elif key in KEYS_ROTATE_CW:
            game.rotate(1)
        elif key in KEYS_ROTATE_CCW:
            game.rotate(-1)
        elif key in KEYS_HOLD:
            game.hold()

    def _key_up(self, key: int) -> None:
        if key in KEYS_LEFT:
            self.shift.release(LEFT)
        elif key in KEYS_RIGHT:
            self.shift.release(RIGHT)
        elif key in KEYS_SOFT_DROP:
            self.game.set_soft_drop(False)

    def _toggle_pause(self) -> None:
        self.game.toggle_pause()
        # Keys released while paused never send KEYUP to the game, so start clean.
        self.shift.clear()
        self.game.set_soft_drop(False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tetris", description="Tetris in pygame.")
    parser.add_argument("--level", type=int, default=1, help="starting level (default 1)")
    parser.add_argument("--scoring", choices=sorted(SCORING_RULES), default="guideline", help="scoring rule set")
    parser.add_argument(
        "--theme", type=str.capitalize, choices=theme_names(), default=theme_names()[0], help="colour theme"
    )
    parser.add_argument("--seed", type=int, default=None, help="seed the piece randomiser for a repeatable game")
    parser.add_argument("--autoplay", action="store_true", help="start straight into a game played by the autoplayer")
    parser.add_argument("--no-ghost", action="store_true", help="hide the ghost piece")
    parser.add_argument("--no-smooth", action="store_true", help="draw falling pieces row by row")
    parser.add_argument("--das", type=float, default=167, help="delayed auto shift in ms (default 167)")
    parser.add_argument("--arr", type=float, default=33, help="auto repeat rate in ms (default 33)")
    parser.add_argument("--highscores", type=Path, default=DEFAULT_PATH, help="high-score file location")
    parser.add_argument("--frames", type=int, default=None, help="quit after N frames (for headless smoke tests)")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.level < 1:
        raise SystemExit("--level must be at least 1")
    if args.das < 0 or args.arr <= 0:
        raise SystemExit("--das must be >= 0 and --arr must be > 0")
    App(args).run(max_frames=args.frames)
