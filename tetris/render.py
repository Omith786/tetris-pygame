"""Everything that touches pygame drawing.

The renderer is read-only with respect to the game: it takes a ``Game`` plus a
small ``HudState`` describing the surrounding screen and paints one frame.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import pygame

from tetris.effects import Effects
from tetris.game import Game, Phase
from tetris.highscore import ScoreEntry
from tetris.pieces import Piece, PieceKind, shape_cells
from tetris.themes import RGB, Theme

CELL = 30
MARGIN = 24
PANEL_WIDTH = 170
GAP = 20
HEADER = 56
FOOTER = 28
BOARD_COLUMNS = 10
BOARD_ROWS = 20

BOARD_LEFT = MARGIN + PANEL_WIDTH + GAP
BOARD_TOP = HEADER
BOARD_WIDTH = BOARD_COLUMNS * CELL
BOARD_HEIGHT = BOARD_ROWS * CELL
WINDOW_SIZE = (BOARD_LEFT + BOARD_WIDTH + GAP + PANEL_WIDTH + MARGIN, HEADER + BOARD_HEIGHT + FOOTER)
RIGHT_PANEL_LEFT = BOARD_LEFT + BOARD_WIDTH + GAP


class Screen(Enum):
    TITLE = "title"
    PLAYING = "playing"
    GAME_OVER = "game_over"


@dataclass(slots=True)
class HudState:
    """Front-end state the renderer needs that is not part of the game rules."""

    screen: Screen = Screen.TITLE
    high_scores: list[ScoreEntry] = field(default_factory=list)
    autoplay: bool = False
    show_ghost: bool = True
    smooth_fall: bool = True
    final_rank: int | None = None
    recorded: bool = True


def blend(colour: RGB, other: RGB, amount: float) -> RGB:
    """Linear mix of two colours; ``amount`` 0 keeps ``colour``, 1 gives ``other``."""
    amount = max(0.0, min(1.0, amount))
    return (
        round(colour[0] + (other[0] - colour[0]) * amount),
        round(colour[1] + (other[1] - colour[1]) * amount),
        round(colour[2] + (other[2] - colour[2]) * amount),
    )


def _format_time(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}:{secs:02d}"


class Renderer:
    def __init__(self, surface: pygame.Surface, theme: Theme) -> None:
        self.surface = surface
        self.theme = theme
        self.font_title = pygame.font.Font(None, 64)
        self.font_large = pygame.font.Font(None, 44)
        self.font_medium = pygame.font.Font(None, 30)
        self.font_small = pygame.font.Font(None, 22)
        self.font_value = pygame.font.Font(None, 34)
        self.well_rect = pygame.Rect(BOARD_LEFT, BOARD_TOP, BOARD_WIDTH, BOARD_HEIGHT)

    # ------------------------------------------------------------------ frame

    def draw(self, game: Game, effects: Effects, hud: HudState) -> None:
        theme = self.theme
        self.surface.fill(theme.background)
        self._draw_header(hud)
        self._draw_well(game, effects, hud)
        self._draw_left_panel(game, hud)
        self._draw_right_panel(game, hud)
        self._draw_footer(hud)

        if hud.screen is Screen.TITLE:
            self._draw_title_overlay(hud)
        elif hud.screen is Screen.GAME_OVER:
            self._draw_game_over_overlay(game, hud)
        elif game.paused:
            self._draw_pause_overlay()

    # --------------------------------------------------------------- sections

    def _draw_header(self, hud: HudState) -> None:
        title = self.font_large.render("TETRIS", True, self.theme.text)
        self.surface.blit(title, title.get_rect(midleft=(MARGIN, HEADER // 2)))
        if hud.autoplay:
            tag = self.font_small.render("AUTOPLAY", True, self.theme.background)
            box = tag.get_rect(midright=(WINDOW_SIZE[0] - MARGIN - 8, HEADER // 2)).inflate(16, 8)
            pygame.draw.rect(self.surface, self.theme.accent, box, border_radius=6)
            self.surface.blit(tag, tag.get_rect(center=box.center))

    def _draw_footer(self, hud: HudState) -> None:
        hint = "P pause   T theme   G ghost   A autoplay"
        text = self.font_small.render(hint, True, self.theme.muted)
        self.surface.blit(text, text.get_rect(midbottom=(WINDOW_SIZE[0] // 2, WINDOW_SIZE[1] - 6)))

    def _draw_well(self, game: Game, effects: Effects, hud: HudState) -> None:
        theme = self.theme
        border = self.well_rect.inflate(8, 8)
        pygame.draw.rect(self.surface, theme.border, border, border_radius=6)
        pygame.draw.rect(self.surface, theme.well, self.well_rect)
        for col in range(1, BOARD_COLUMNS):
            x = BOARD_LEFT + col * CELL
            pygame.draw.line(self.surface, theme.grid, (x, BOARD_TOP), (x, BOARD_TOP + BOARD_HEIGHT - 1))
        for row in range(1, BOARD_ROWS):
            y = BOARD_TOP + row * CELL
            pygame.draw.line(self.surface, theme.grid, (BOARD_LEFT, y), (BOARD_LEFT + BOARD_WIDTH - 1, y))

        previous_clip = self.surface.get_clip()
        self.surface.set_clip(self.well_rect)
        hidden = game.board.hidden_rows
        clearing = set(game.clearing_rows) if game.phase is Phase.CLEARING else set()
        flash = 1.0 - game.clear_progress

        for y, row in enumerate(game.board.grid):
            for x, kind in enumerate(row):
                if kind is None:
                    continue
                colour = theme.colour(kind)
                if y in clearing:
                    colour = blend(colour, (255, 255, 255), 0.35 + 0.65 * flash)
                self._draw_cell(x, y - hidden, colour)

        for lock_flash in effects.flashes:
            for x, y in lock_flash.cells:
                self._draw_overlay_cell(x, y - hidden, (255, 255, 255), int(110 * lock_flash.strength))

        if game.active is not None and game.phase is Phase.PLAYING:
            if hud.show_ghost and game.ghost is not None and game.ghost != game.active:
                self._draw_ghost(game.ghost, hidden)
            offset = game.fall_progress * CELL if hud.smooth_fall else 0.0
            self._draw_piece(game.active, hidden, offset, game.lock_progress)

        self._draw_popups(effects)
        self.surface.set_clip(previous_clip)

    def _draw_left_panel(self, game: Game, hud: HudState) -> None:
        theme = self.theme
        left = MARGIN
        hold_box = pygame.Rect(left, BOARD_TOP, PANEL_WIDTH, 118)
        self._panel(hold_box, "HOLD")
        if game.hold_kind is not None:
            colour = theme.colour(game.hold_kind) if game.can_hold else blend(theme.colour(game.hold_kind), theme.panel, 0.65)
            self._draw_preview(game.hold_kind, hold_box.centerx, hold_box.top + 70, 24, colour)

        stats_box = pygame.Rect(left, hold_box.bottom + 16, PANEL_WIDTH, 318)
        self._panel(stats_box, "STATS")
        best = max(game.score, hud.high_scores[0].score if hud.high_scores else 0)
        rows = (
            ("SCORE", f"{game.score:,}"),
            ("BEST", f"{best:,}"),
            ("LEVEL", str(game.level)),
            ("LINES", str(game.lines)),
            ("TIME", _format_time(game.stats.elapsed)),
        )
        y = stats_box.top + 42
        for label, value in rows:
            label_surface = self.font_small.render(label, True, theme.muted)
            value_surface = self.font_value.render(value, True, theme.text)
            self.surface.blit(label_surface, (left + 16, y))
            self.surface.blit(value_surface, (left + 16, y + 17))
            y += 54

    def _draw_right_panel(self, game: Game, hud: HudState) -> None:
        theme = self.theme
        left = RIGHT_PANEL_LEFT
        queue = game.next_queue
        next_box = pygame.Rect(left, BOARD_TOP, PANEL_WIDTH, 60 + 76 + 62 * (len(queue) - 1))
        self._panel(next_box, "NEXT")
        y = next_box.top + 74
        for index, kind in enumerate(queue):
            size = 24 if index == 0 else 18
            self._draw_preview(kind, next_box.centerx, y, size, theme.colour(kind))
            y += 76 if index == 0 else 62

        info_box = pygame.Rect(left, next_box.bottom + 16, PANEL_WIDTH, BOARD_TOP + BOARD_HEIGHT - next_box.bottom - 16)
        self._panel(info_box, "MODE")
        details = (
            ("RULES", game.rule.name.upper()),
            ("THEME", theme.name.upper()),
            ("COMBO", str(max(game.combo, 0))),
        )
        y = info_box.top + 42
        for label, value in details:
            self.surface.blit(self.font_small.render(label, True, theme.muted), (left + 16, y))
            self.surface.blit(self.font_medium.render(value, True, theme.text), (left + 16, y + 17))
            y += 48

    # ----------------------------------------------------------------- pieces

    def _cell_rect(self, x: int, y: float) -> pygame.Rect:
        return pygame.Rect(BOARD_LEFT + x * CELL, round(BOARD_TOP + y * CELL), CELL, CELL)

    def _draw_cell(self, x: int, y: float, colour: RGB) -> None:
        self._draw_block(self._cell_rect(x, y), colour)

    def _draw_block(self, rect: pygame.Rect, colour: RGB) -> None:
        """A bevelled block: flat face, lighter top edge, darker bottom edge."""
        inner = rect.inflate(-2, -2)
        pygame.draw.rect(self.surface, blend(colour, (0, 0, 0), 0.28), inner, border_radius=4)
        face = inner.copy()
        face.height -= 3
        pygame.draw.rect(self.surface, colour, face, border_radius=4)
        highlight = pygame.Rect(face.left + 3, face.top + 2, face.width - 6, 3)
        pygame.draw.rect(self.surface, blend(colour, (255, 255, 255), 0.4), highlight, border_radius=2)

    def _draw_overlay_cell(self, x: int, y: float, colour: RGB, alpha: int) -> None:
        overlay = pygame.Surface((CELL - 2, CELL - 2), pygame.SRCALPHA)
        overlay.fill((*colour, max(0, min(255, alpha))))
        self.surface.blit(overlay, self._cell_rect(x, y).inflate(-2, -2))

    def _draw_piece(self, piece: Piece, hidden: int, pixel_offset: float, lock_progress: float) -> None:
        colour = self.theme.colour(piece.kind)
        # Brighten slightly as the lock timer runs down so resting pieces read as "about to set".
        colour = blend(colour, (255, 255, 255), 0.25 * lock_progress)
        for x, y in piece.cells():
            rect = self._cell_rect(x, y - hidden)
            rect.y += round(pixel_offset)
            self._draw_block(rect, colour)

    def _draw_ghost(self, piece: Piece, hidden: int) -> None:
        colour = self.theme.colour(piece.kind)
        fill = pygame.Surface((CELL - 2, CELL - 2), pygame.SRCALPHA)
        fill.fill((*colour, 45))
        for x, y in piece.cells():
            rect = self._cell_rect(x, y - hidden).inflate(-2, -2)
            self.surface.blit(fill, rect)
            pygame.draw.rect(self.surface, colour, rect, width=2, border_radius=4)

    def _draw_preview(self, kind: PieceKind, centre_x: int, centre_y: int, size: int, colour: RGB) -> None:
        cells = shape_cells(kind)
        xs = [x for x, _ in cells]
        ys = [y for _, y in cells]
        width = (max(xs) - min(xs) + 1) * size
        height = (max(ys) - min(ys) + 1) * size
        origin_x = centre_x - width / 2 - min(xs) * size
        origin_y = centre_y - height / 2 - min(ys) * size
        for x, y in cells:
            rect = pygame.Rect(round(origin_x + x * size), round(origin_y + y * size), size, size)
            self._draw_block(rect, colour)

    # ------------------------------------------------------------ decorations

    def _panel(self, rect: pygame.Rect, title: str) -> None:
        pygame.draw.rect(self.surface, self.theme.panel, rect, border_radius=10)
        pygame.draw.rect(self.surface, self.theme.border, rect, width=2, border_radius=10)
        label = self.font_small.render(title, True, self.theme.accent)
        self.surface.blit(label, (rect.left + 16, rect.top + 14))

    def _draw_popups(self, effects: Effects) -> None:
        y = BOARD_TOP + BOARD_HEIGHT * 0.38
        for popup in reversed(effects.popups[-2:]):
            line_y = y - popup.rise * 40
            for index, text in enumerate(popup.lines):
                font = self.font_medium if index < len(popup.lines) - 1 else self.font_small
                colour = self.theme.accent if text.startswith("+") else self.theme.text
                surface = self._outlined(text, font, colour)
                surface.set_alpha(round(255 * popup.alpha))
                self.surface.blit(surface, surface.get_rect(center=(self.well_rect.centerx, round(line_y))))
                line_y += 28
            y -= 28 * len(popup.lines) + 12

    def _outlined(self, text: str, font: pygame.font.Font, colour: RGB) -> pygame.Surface:
        """Text with a dark outline so it stays readable over any stack colour."""
        base = font.render(text, True, colour)
        outline = font.render(text, True, (0, 0, 0))
        surface = pygame.Surface((base.get_width() + 4, base.get_height() + 4), pygame.SRCALPHA)
        for dx, dy in ((0, 0), (4, 0), (0, 4), (4, 4), (2, 0), (0, 2), (4, 2), (2, 4)):
            surface.blit(outline, (dx, dy))
        surface.blit(base, (2, 2))
        return surface

    def _dim_well(self, alpha: int = 200) -> None:
        veil = pygame.Surface(self.well_rect.size, pygame.SRCALPHA)
        veil.fill((*self.theme.background, alpha))
        self.surface.blit(veil, self.well_rect)

    def _centre_lines(self, lines: list[tuple[str, pygame.font.Font, RGB]], top: int) -> None:
        y = top
        for text, font, colour in lines:
            if text:
                surface = font.render(text, True, colour)
                self.surface.blit(surface, surface.get_rect(midtop=(self.well_rect.centerx, y)))
            y += font.get_linesize() + 4

    def _draw_pause_overlay(self) -> None:
        theme = self.theme
        self._dim_well()
        self._centre_lines(
            [
                ("PAUSED", self.font_large, theme.text),
                ("", self.font_small, theme.muted),
                ("P / Esc   resume", self.font_small, theme.muted),
                ("R   restart", self.font_small, theme.muted),
                ("Q   quit", self.font_small, theme.muted),
            ],
            BOARD_TOP + 200,
        )

    def _draw_title_overlay(self, hud: HudState) -> None:
        theme = self.theme
        self._dim_well(225)
        lines: list[tuple[str, pygame.font.Font, RGB]] = [
            ("TETRIS", self.font_title, theme.accent),
            ("Press Enter to play", self.font_medium, theme.text),
            ("", self.font_small, theme.muted),
            ("Left / Right   move", self.font_small, theme.muted),
            ("Down   soft drop", self.font_small, theme.muted),
            ("Space   hard drop", self.font_small, theme.muted),
            ("Up / X   rotate right", self.font_small, theme.muted),
            ("Z / Ctrl   rotate left", self.font_small, theme.muted),
            ("C / Shift   hold", self.font_small, theme.muted),
            ("", self.font_small, theme.muted),
            ("HIGH SCORES", self.font_medium, theme.accent),
        ]
        if hud.high_scores:
            for rank, entry in enumerate(hud.high_scores, start=1):
                lines.append((f"{rank}.  {entry.score:>8,}   L{entry.level}", self.font_small, theme.text))
        else:
            lines.append(("No scores yet", self.font_small, theme.muted))
        self._centre_lines(lines, BOARD_TOP + 60)

    def _draw_game_over_overlay(self, game: Game, hud: HudState) -> None:
        theme = self.theme
        self._dim_well(215)
        if not hud.recorded:
            verdict = "Autoplay games are not recorded"
        elif hud.final_rank == 1:
            verdict = "New high score!"
        elif hud.final_rank is not None:
            verdict = f"Ranked #{hud.final_rank}"
        else:
            verdict = ""
        self._centre_lines(
            [
                ("GAME OVER", self.font_large, theme.text),
                ("", self.font_small, theme.muted),
                (f"{game.score:,}", self.font_title, theme.accent),
                (verdict, self.font_medium, theme.text),
                ("", self.font_small, theme.muted),
                (f"Lines {game.lines}   Level {game.level}", self.font_small, theme.muted),
                (f"Tetrises {game.stats.tetrises}   T-spins {game.stats.tspins}", self.font_small, theme.muted),
                (f"Best combo {max(game.stats.max_combo, 0)}   Time {_format_time(game.stats.elapsed)}", self.font_small, theme.muted),
                ("", self.font_small, theme.muted),
                ("Enter   play again", self.font_small, theme.text),
                ("Esc   quit", self.font_small, theme.text),
            ],
            BOARD_TOP + 150,
        )
