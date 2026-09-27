"""Scoring rules, level progression and the gravity curve.

Scoring is a small strategy interface so that alternative rule sets can be
dropped in without touching the game loop. Two are provided: modern guideline
scoring (T-spins, back-to-back and combos) and a simpler classic rule set with
NES-style line values.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from tetris.mechanics import TSpin

LINES_PER_LEVEL = 10
# Beyond this level the guideline formula stops being meaningful (it eventually
# goes negative), and the pieces are already dropping at roughly 20 rows a frame.
MAX_GRAVITY_LEVEL = 20


@dataclass(frozen=True, slots=True)
class ClearContext:
    """Everything a scoring rule needs to price one piece lock."""

    lines: int
    tspin: TSpin
    level: int
    combo: int  # 0 for the first clear in a chain, 1 for the second, and so on
    back_to_back: bool  # this clear continues a chain of "difficult" clears


class ScoringRule(Protocol):
    """Interface for a scoring rule set."""

    name: str

    def clear_points(self, ctx: ClearContext) -> int:
        """Points for a lock that cleared lines or was a T-spin."""
        ...

    def soft_drop_points(self, cells: int) -> int: ...

    def hard_drop_points(self, cells: int) -> int: ...


def is_difficult(lines: int, tspin: TSpin) -> bool:
    """Whether a clear counts towards back-to-back chains (Tetrises and line-clearing T-spins)."""
    return lines == 4 or (tspin is not TSpin.NONE and lines > 0)


class GuidelineScoring:
    """Modern guideline values: T-spins, a 1.5x back-to-back bonus and combo points."""

    name = "guideline"

    _LINES = {0: 0, 1: 100, 2: 300, 3: 500, 4: 800}
    _TSPIN = {0: 400, 1: 800, 2: 1200, 3: 1600}
    _TSPIN_MINI = {0: 100, 1: 200, 2: 400}
    _COMBO = 50

    def clear_points(self, ctx: ClearContext) -> int:
        if ctx.tspin is TSpin.FULL:
            base = self._TSPIN[ctx.lines]
        elif ctx.tspin is TSpin.MINI:
            # The guideline has no mini triple; should one ever occur, pay it as a plain triple.
            base = self._TSPIN_MINI.get(ctx.lines, self._LINES[ctx.lines])
        else:
            base = self._LINES[ctx.lines]
        points = base * ctx.level
        if ctx.back_to_back and is_difficult(ctx.lines, ctx.tspin):
            points = points * 3 // 2
        if ctx.lines > 0 and ctx.combo > 0:
            points += self._COMBO * ctx.combo * ctx.level
        return points

    def soft_drop_points(self, cells: int) -> int:
        return cells

    def hard_drop_points(self, cells: int) -> int:
        return 2 * cells


class ClassicScoring:
    """NES-style line values scaled by level, with no T-spin, combo or back-to-back bonuses."""

    name = "classic"

    _LINES = {0: 0, 1: 40, 2: 100, 3: 300, 4: 1200}

    def clear_points(self, ctx: ClearContext) -> int:
        return self._LINES[ctx.lines] * ctx.level

    def soft_drop_points(self, cells: int) -> int:
        return cells

    def hard_drop_points(self, cells: int) -> int:
        return cells


SCORING_RULES: dict[str, ScoringRule] = {
    GuidelineScoring.name: GuidelineScoring(),
    ClassicScoring.name: ClassicScoring(),
}


def level_for_lines(lines: int, start_level: int = 1) -> int:
    """Fixed-goal progression: one level per ten lines on top of the starting level."""
    return start_level + lines // LINES_PER_LEVEL


def gravity_interval(level: int) -> float:
    """Seconds for the active piece to fall one row at ``level`` (guideline curve).

    Level 1 is one row per second; by level 15 a piece falls about 140 rows a
    second, which in practice means it lands the frame it spawns.
    """
    effective = max(1, min(level, MAX_GRAVITY_LEVEL))
    return (0.8 - (effective - 1) * 0.007) ** (effective - 1)


_CLEAR_NAMES = {1: "SINGLE", 2: "DOUBLE", 3: "TRIPLE", 4: "TETRIS"}


def describe_clear(lines: int, tspin: TSpin) -> str:
    """Human-readable label such as ``"T-SPIN DOUBLE"`` for on-screen callouts."""
    if tspin is TSpin.NONE:
        return _CLEAR_NAMES.get(lines, "")
    prefix = "T-SPIN MINI" if tspin is TSpin.MINI else "T-SPIN"
    return f"{prefix} {_CLEAR_NAMES[lines]}" if lines else prefix
