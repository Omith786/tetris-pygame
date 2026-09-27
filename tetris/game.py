"""The game state machine: gravity, lock delay, hold, scoring and line clears.

``Game`` knows nothing about pygame. Front ends call the control methods
(``move``, ``rotate``, ``hard_drop`` ...) and advance time with ``tick``; the
game reports anything worth animating through ``drain_events``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

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
from tetris.pieces import Cell, Piece, PieceKind
from tetris.randomizer import SevenBag
from tetris.scoring import SCORING_RULES, ClearContext, gravity_interval, is_difficult, level_for_lines


class Phase(Enum):
    PLAYING = "playing"
    CLEARING = "clearing"  # full rows are shown flashing before they collapse
    GAME_OVER = "game_over"


class PieceSource(Protocol):
    """Anything that can deal pieces; ``SevenBag`` in normal play, a fixed list in tests."""

    def next(self) -> PieceKind: ...

    def peek(self, count: int) -> list[PieceKind]: ...


@dataclass(frozen=True, slots=True)
class LockEvent:
    cells: tuple[Cell, ...]
    kind: PieceKind


@dataclass(frozen=True, slots=True)
class ClearEvent:
    """A scoring lock. ``lines`` may be 0 for a T-spin that cleared nothing."""

    rows: tuple[int, ...]
    lines: int
    tspin: TSpin
    back_to_back: bool
    combo: int
    points: int


@dataclass(frozen=True, slots=True)
class LevelUpEvent:
    level: int


@dataclass(frozen=True, slots=True)
class GameOverEvent:
    reason: str


GameEvent = LockEvent | ClearEvent | LevelUpEvent | GameOverEvent


@dataclass(slots=True)
class GameConfig:
    """Tunable rules. Defaults follow the modern guideline where one exists."""

    start_level: int = 1
    scoring: str = "guideline"
    lock_delay: float = 0.5
    # Moving or rotating a grounded piece restarts its lock timer, but only this
    # many times per row reached, so a piece cannot be stalled forever.
    max_lock_resets: int = 15
    line_clear_delay: float = 0.3
    soft_drop_factor: float = 20.0
    preview_count: int = 5

    def __post_init__(self) -> None:
        if self.scoring not in SCORING_RULES:
            raise ValueError(f"unknown scoring rule {self.scoring!r}; choose from {sorted(SCORING_RULES)}")
        if self.start_level < 1:
            raise ValueError("start_level must be at least 1")


@dataclass(slots=True)
class GameStats:
    pieces: int = 0
    tetrises: int = 0
    tspins: int = 0
    max_combo: int = 0
    elapsed: float = 0.0


class Game:
    """A single game of Tetris.

    ``seed`` makes the piece sequence reproducible. ``board`` and ``pieces`` can
    be supplied to start from a prepared position, which the tests rely on.
    """

    def __init__(
        self,
        config: GameConfig | None = None,
        seed: int | None = None,
        board: Board | None = None,
        pieces: PieceSource | None = None,
    ) -> None:
        self.config = config or GameConfig()
        self.rule = SCORING_RULES[self.config.scoring]
        self.board = board or Board()
        self.pieces: PieceSource = pieces or SevenBag(seed)
        self.active: Piece | None = None
        self.hold_kind: PieceKind | None = None
        self.can_hold = True
        self.score = 0
        self.lines = 0
        self.level = self.config.start_level
        self.combo = -1
        self.phase = Phase.PLAYING
        self.paused = False
        self.stats = GameStats()
        self.spawn_id = 0
        self.clearing_rows: tuple[int, ...] = ()
        self._b2b_ready = False
        self._soft_drop = False
        self._gravity_acc = 0.0
        self._lock_timer = 0.0
        self._lock_resets = 0
        self._lowest_y = 0
        self._last_kick: int | None = None
        self._clear_timer = 0.0
        self._events: list[GameEvent] = []
        self._spawn(self.pieces.next())

    # ------------------------------------------------------------------ queries

    @property
    def is_over(self) -> bool:
        return self.phase is Phase.GAME_OVER

    @property
    def next_queue(self) -> list[PieceKind]:
        return self.pieces.peek(self.config.preview_count)

    @property
    def ghost(self) -> Piece | None:
        """Where the active piece would land if hard dropped now."""
        if self.active is None:
            return None
        return self.active.shifted(0, drop_distance(self.board, self.active))

    @property
    def fall_progress(self) -> float:
        """Fraction (0-1) of the way to the next gravity step, used to draw smooth falling."""
        if self.active is None or self.phase is not Phase.PLAYING or is_grounded(self.board, self.active):
            return 0.0
        return min(self._gravity_acc / self._fall_interval(), 1.0)

    @property
    def lock_progress(self) -> float:
        """Fraction (0-1) of the lock delay used up, so the renderer can fade a resting piece."""
        if self.config.lock_delay <= 0:
            return 0.0
        return min(self._lock_timer / self.config.lock_delay, 1.0)

    @property
    def clear_progress(self) -> float:
        """Fraction (0-1) of the line-clear animation that has elapsed."""
        if self.phase is not Phase.CLEARING or self.config.line_clear_delay <= 0:
            return 0.0
        return 1.0 - max(self._clear_timer, 0.0) / self.config.line_clear_delay

    def drain_events(self) -> list[GameEvent]:
        """Return and forget everything that happened since the last call."""
        events, self._events = self._events, []
        return events

    # ----------------------------------------------------------------- controls

    def move(self, dx: int) -> bool:
        """Shift the active piece sideways by ``dx`` columns (one step). Returns success."""
        if not self._controllable():
            return False
        assert self.active is not None
        moved = try_shift(self.board, self.active, dx, 0)
        if moved is None:
            return False
        self._manoeuvre(moved, kick=None)
        return True

    def rotate(self, direction: int) -> bool:
        """Rotate clockwise (+1) or anticlockwise (-1) with SRS wall kicks. Returns success."""
        if not self._controllable():
            return False
        assert self.active is not None
        result = try_rotate(self.board, self.active, direction)
        if result is None:
            return False
        self._manoeuvre(result.piece, kick=result.kick_index)
        return True

    def set_soft_drop(self, active: bool) -> None:
        """Start or stop soft dropping (gravity multiplied by ``soft_drop_factor``)."""
        if active and not self._soft_drop:
            # Without this, gravity time banked before the key press would be
            # spent instantly at soft-drop speed and the piece would jump rows.
            self._gravity_acc = min(self._gravity_acc, gravity_interval(self.level) / self.config.soft_drop_factor)
        self._soft_drop = active

    def hard_drop(self) -> None:
        """Drop the active piece straight down and lock it immediately."""
        if not self._controllable():
            return
        assert self.active is not None
        distance = drop_distance(self.board, self.active)
        if distance:
            self.active = self.active.shifted(0, distance)
            self._last_kick = None
        self.score += self.rule.hard_drop_points(distance)
        self._lock()

    def hold(self) -> bool:
        """Swap the active piece with the held one (once per piece). Returns success."""
        if not self._controllable() or not self.can_hold:
            return False
        assert self.active is not None
        current = self.active.kind
        replacement = self.pieces.next() if self.hold_kind is None else self.hold_kind
        self.hold_kind = current
        self.can_hold = False
        self._spawn(replacement)
        return True

    def toggle_pause(self) -> None:
        if not self.is_over:
            self.paused = not self.paused

    # --------------------------------------------------------------------- time

    def tick(self, dt: float) -> None:
        """Advance the simulation by ``dt`` seconds."""
        if self.paused or self.is_over:
            return
        self.stats.elapsed += dt
        if self.phase is Phase.CLEARING:
            self._clear_timer -= dt
            if self._clear_timer <= 0:
                self._finish_clear()
            return
        self._apply_gravity(dt)
        if self.phase is Phase.PLAYING and self.active is not None:
            self._update_lock(dt)

    # ---------------------------------------------------------------- internals

    def _controllable(self) -> bool:
        return self.active is not None and self.phase is Phase.PLAYING and not self.paused

    def _fall_interval(self) -> float:
        interval = gravity_interval(self.level)
        return interval / self.config.soft_drop_factor if self._soft_drop else interval

    def _manoeuvre(self, piece: Piece, kick: int | None) -> None:
        """Apply a player move or rotation, handling lock-delay resets."""
        assert self.active is not None
        touching = is_grounded(self.board, self.active) or is_grounded(self.board, piece)
        self._set_active(piece)
        self._last_kick = kick
        if touching and self._lock_resets < self.config.max_lock_resets:
            self._lock_timer = 0.0
            self._lock_resets += 1

    def _set_active(self, piece: Piece) -> None:
        self.active = piece
        if piece.y > self._lowest_y:
            # Reaching new ground earns a fresh set of lock resets.
            self._lowest_y = piece.y
            self._lock_resets = 0
            self._lock_timer = 0.0

    def _apply_gravity(self, dt: float) -> None:
        assert self.active is not None
        if is_grounded(self.board, self.active):
            self._gravity_acc = 0.0
            return
        interval = self._fall_interval()
        self._gravity_acc += dt
        # High levels need several rows per frame, hence a loop rather than one step.
        while self._gravity_acc >= interval:
            moved = try_shift(self.board, self.active, 0, 1)
            if moved is None:
                self._gravity_acc = 0.0
                break
            self._gravity_acc -= interval
            self._set_active(moved)
            self._last_kick = None
            if self._soft_drop:
                self.score += self.rule.soft_drop_points(1)

    def _update_lock(self, dt: float) -> None:
        assert self.active is not None
        if not is_grounded(self.board, self.active):
            self._lock_timer = 0.0
            return
        self._lock_timer += dt
        if self._lock_timer >= self.config.lock_delay:
            self._lock()

    def _lock(self) -> None:
        assert self.active is not None
        piece = self.active
        tspin = detect_tspin(self.board, piece, self._last_kick)
        cells = piece.cells()
        self.board.place(cells, piece.kind)
        self.active = None
        self.stats.pieces += 1
        self._events.append(LockEvent(cells, piece.kind))

        # Lock out: the whole piece came to rest above the visible field.
        if all(y < self.board.hidden_rows for _, y in cells):
            self._game_over("lock out")
            return

        rows = tuple(self.board.full_rows())
        self._score_lock(len(rows), rows, tspin)
        self.can_hold = True

        if rows:
            self.lines += len(rows)
            new_level = level_for_lines(self.lines, self.config.start_level)
            if new_level > self.level:
                self.level = new_level
                self._events.append(LevelUpEvent(new_level))
            if self.config.line_clear_delay > 0:
                self.phase = Phase.CLEARING
                self.clearing_rows = rows
                self._clear_timer = self.config.line_clear_delay
                return
            self.board.clear_rows(rows)

        self._spawn(self.pieces.next())

    def _score_lock(self, lines: int, rows: tuple[int, ...], tspin: TSpin) -> None:
        self.combo = self.combo + 1 if lines else -1
        if lines == 0 and tspin is TSpin.NONE:
            return
        difficult = is_difficult(lines, tspin)
        back_to_back = difficult and self._b2b_ready
        ctx = ClearContext(lines, tspin, self.level, max(self.combo, 0), back_to_back)
        points = self.rule.clear_points(ctx)
        # A T-spin that clears nothing neither extends nor breaks a back-to-back chain.
        if lines:
            self._b2b_ready = difficult
        self.score += points
        if lines == 4:
            self.stats.tetrises += 1
        if tspin is not TSpin.NONE:
            self.stats.tspins += 1
        self.stats.max_combo = max(self.stats.max_combo, self.combo)
        self._events.append(ClearEvent(rows, lines, tspin, back_to_back, self.combo, points))

    def _finish_clear(self) -> None:
        self.board.clear_rows(self.clearing_rows)
        self.clearing_rows = ()
        self.phase = Phase.PLAYING
        self._spawn(self.pieces.next())

    def _spawn(self, kind: PieceKind) -> None:
        piece = spawn_position(kind, self.board)
        if not self.board.fits(piece.cells()):
            # Block out: there is no room for the new piece.
            self.active = None
            self._game_over("block out")
            return
        # Guideline behaviour: step straight into view if there is room.
        piece = try_shift(self.board, piece, 0, 1) or piece
        self.active = piece
        self.spawn_id += 1
        self._gravity_acc = 0.0
        self._lock_timer = 0.0
        self._lock_resets = 0
        self._lowest_y = piece.y
        self._last_kick = None

    def _game_over(self, reason: str) -> None:
        self.phase = Phase.GAME_OVER
        self._soft_drop = False
        self._events.append(GameOverEvent(reason))
