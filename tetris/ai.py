"""A heuristic autoplayer used for the demo mode and as an example extension.

It tries every rotation and column for the current piece (and the hold
alternative), scores each resulting board with four weighted features, and
then plays the best placement through the normal ``Game`` controls, so it is
bound by exactly the same rules as a human.

The feature weights come from Yiyuan Lee's well-known genetic-algorithm tuned
player: aggregate height, completed lines, holes and bumpiness.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum

from tetris.board import Board
from tetris.game import Game, Phase
from tetris.mechanics import drop_distance, spawn_position, try_rotate, try_shift
from tetris.pieces import Piece, PieceKind
from tetris.scoring import gravity_interval


@dataclass(frozen=True, slots=True)
class Weights:
    height: float = -0.510066
    lines: float = 0.760666
    holes: float = -0.35663
    bumpiness: float = -0.184483


class Action(Enum):
    LEFT = "left"
    RIGHT = "right"
    ROTATE_CW = "rotate_cw"
    ROTATE_CCW = "rotate_ccw"
    HOLD = "hold"
    DROP = "drop"


@dataclass(frozen=True, slots=True)
class Placement:
    """A reachable resting position and the inputs that get the piece there."""

    piece: Piece
    actions: tuple[Action, ...]
    score: float


# Rotation prefixes tried from the spawn orientation. Reaching state 3 with one
# anticlockwise turn is both quicker and more likely to fit than three clockwise.
_ROTATION_PLANS: tuple[tuple[Action, ...], ...] = (
    (),
    (Action.ROTATE_CW,),
    (Action.ROTATE_CW, Action.ROTATE_CW),
    (Action.ROTATE_CCW,),
)


def evaluate(board: Board, lines_cleared: int, weights: Weights = Weights()) -> float:
    """Score a board after a placement; higher is better."""
    heights = board.column_heights()
    bumpiness = sum(abs(a - b) for a, b in zip(heights, heights[1:], strict=False))
    return (
        weights.height * sum(heights)
        + weights.lines * lines_cleared
        + weights.holes * board.count_holes()
        + weights.bumpiness * bumpiness
    )


def _simulate(board: Board, piece: Piece) -> tuple[Board, int]:
    cells = piece.cells()
    result = board.copy()
    result.place(cells, piece.kind)
    # Only rows the piece touched can have just become full.
    full = [y for y in {y for _, y in cells} if all(cell is not None for cell in result.grid[y])]
    return result, result.clear_rows(full)


def candidate_placements(board: Board, piece: Piece, weights: Weights = Weights()) -> list[Placement]:
    """Every placement reachable by rotating first, then shifting, then hard dropping."""
    placements: list[Placement] = []
    seen: set[tuple[int, int, int]] = set()
    plans = _ROTATION_PLANS[:1] if piece.kind is PieceKind.O else _ROTATION_PLANS
    for rotation_plan in plans:
        rotated: Piece | None = piece
        for action in rotation_plan:
            result = try_rotate(board, rotated, 1 if action is Action.ROTATE_CW else -1) if rotated else None
            rotated = result.piece if result else None
        if rotated is None:
            continue
        for step, shift_action in ((-1, Action.LEFT), (1, Action.RIGHT)):
            current = rotated
            shifts: list[Action] = []
            while True:
                landed = current.shifted(0, drop_distance(board, current))
                key = (landed.x, landed.y, landed.rotation)
                if key not in seen:
                    seen.add(key)
                    after, cleared = _simulate(board, landed)
                    actions = (*rotation_plan, *shifts, Action.DROP)
                    placements.append(Placement(landed, actions, evaluate(after, cleared, weights)))
                moved = try_shift(board, current, step, 0)
                if moved is None:
                    break
                current = moved
                shifts.append(shift_action)
    return placements


def best_placement(board: Board, piece: Piece, weights: Weights = Weights()) -> Placement | None:
    """The highest-scoring reachable placement, or ``None`` if the piece cannot move at all."""
    candidates = candidate_placements(board, piece, weights)
    return max(candidates, key=lambda p: p.score, default=None)


class AutoPlayer:
    """Drives a ``Game`` one input at a time so its play is visible on screen."""

    def __init__(self, game: Game, action_interval: float = 0.05, weights: Weights = Weights()) -> None:
        self.game = game
        self.action_interval = action_interval
        self.weights = weights
        self._queue: deque[Action] = deque()
        self._planned_for = -1
        self._cooldown = 0.0

    def reset(self, game: Game) -> None:
        """Attach to a new game."""
        self.game = game
        self._queue.clear()
        self._planned_for = -1
        self._cooldown = 0.0

    def plan(self) -> None:
        """Choose a placement for the current piece, preferring hold if that scores better."""
        game = self.game
        self._queue.clear()
        self._planned_for = game.spawn_id
        if game.active is None:
            return
        best = best_placement(game.board, game.active, self.weights)
        if game.can_hold:
            alternative_kind = game.hold_kind or game.next_queue[0]
            alternative = best_placement(game.board, spawn_position(alternative_kind, game.board), self.weights)
            if alternative is not None and (best is None or alternative.score > best.score):
                # Holding spawns a new piece, which triggers a fresh plan.
                self._queue.append(Action.HOLD)
                return
        if best is not None:
            self._queue.extend(best.actions)
        else:
            self._queue.append(Action.DROP)

    def update(self, dt: float) -> None:
        """Advance the autoplayer; call once per frame before ``Game.tick``."""
        game = self.game
        if game.phase is not Phase.PLAYING or game.paused or game.active is None:
            return
        if game.spawn_id != self._planned_for:
            self.plan()
        self._cooldown -= dt
        while self._queue and self._cooldown <= 0:
            self._cooldown += self._pace()
            if not self._perform(self._queue.popleft()):
                # Gravity can block a planned shift at high speeds; settle for dropping.
                self._queue.clear()
                self._queue.append(Action.DROP)
            if game.spawn_id != self._planned_for:
                break  # the piece was dropped or held; plan the next one next frame
        if not self._queue:
            # Do not bank idle time, or the next piece would get a burst of instant moves.
            self._cooldown = max(self._cooldown, 0.0)

    def _pace(self) -> float:
        # At high levels the piece would hit the stack before a leisurely input
        # sequence finished, so keep each input well inside one gravity step.
        return min(self.action_interval, gravity_interval(self.game.level) / 2)

    def _perform(self, action: Action) -> bool:
        game = self.game
        match action:
            case Action.LEFT:
                return game.move(-1)
            case Action.RIGHT:
                return game.move(1)
            case Action.ROTATE_CW:
                return game.rotate(1)
            case Action.ROTATE_CCW:
                return game.rotate(-1)
            case Action.HOLD:
                return game.hold()
            case Action.DROP:
                game.hard_drop()
                return True
        return False
