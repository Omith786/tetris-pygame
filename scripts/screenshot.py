"""Render a mid-game frame headlessly and save it as a PNG.

The autoplayer plays a seeded game through the real game loop and renderer, so
the image shows exactly what the game draws. Usage:

    python scripts/screenshot.py [--output docs/screenshot.png] [--seed 5] [--pieces 40]
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Must be set before pygame is imported so no window is ever opened.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402

from tetris.ai import AutoPlayer, Weights  # noqa: E402
from tetris.effects import Effects  # noqa: E402
from tetris.game import Game, GameConfig, Phase  # noqa: E402
from tetris.render import WINDOW_SIZE, HudState, Renderer, Screen  # noqa: E402
from tetris.themes import theme_by_name, theme_names  # noqa: E402

FRAME = 1 / 60
# The default weights keep the stack almost flat, which makes a dull picture.
# These tolerate height and avoid small clears, so the bot builds a stack and
# waits for Tetrises: riskier play, but a more representative mid-game frame.
SHOWCASE_WEIGHTS = Weights(height=-0.05, lines=-0.6, holes=-1.2, bumpiness=-0.25)
MIN_STACK_HEIGHT = 6


def capture(output: Path, seed: int, pieces: int, theme: str) -> None:
    pygame.init()
    surface = pygame.display.set_mode(WINDOW_SIZE)
    game = Game(GameConfig(start_level=3), seed=seed)
    bot = AutoPlayer(game, action_interval=0.08, weights=SHOWCASE_WEIGHTS)
    effects = Effects()

    # Play until enough pieces have been placed, then wait for a frame with a
    # piece high in the well (so the ghost is visible) and a Tetris callout on screen.
    for _ in range(200_000):
        bot.update(FRAME)
        game.tick(FRAME)
        effects.handle(game.drain_events())
        effects.update(FRAME)
        if game.is_over:
            raise SystemExit("the autoplayer topped out before the screenshot; try another --seed")
        ready = (
            game.stats.pieces >= pieces
            and game.phase is Phase.PLAYING
            and game.active is not None
            and 3 <= game.active.y <= 6
            and game.hold_kind is not None
            and max(game.board.column_heights()) >= MIN_STACK_HEIGHT
            and any(p.alpha > 0.9 and "TETRIS" in p.lines for p in effects.popups)
        )
        if ready:
            break
    else:
        raise SystemExit("no suitable frame found; try a different --seed or --pieces")

    hud = HudState(screen=Screen.PLAYING, autoplay=True)
    Renderer(surface, theme_by_name(theme)).draw(game, effects, hud)
    output.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(surface, str(output))
    pygame.quit()
    print(f"saved {output} (score {game.score}, lines {game.lines}, level {game.level})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output", type=Path, default=Path("docs/screenshot.png"))
    parser.add_argument("--seed", type=int, default=5)
    parser.add_argument("--pieces", type=int, default=40)
    parser.add_argument("--theme", type=str.capitalize, choices=theme_names(), default=theme_names()[0])
    args = parser.parse_args()
    capture(args.output, args.seed, args.pieces, args.theme)


if __name__ == "__main__":
    main()
