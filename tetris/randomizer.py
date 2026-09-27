"""The 7-bag piece randomiser."""

from __future__ import annotations

import random
from collections import deque

from tetris.pieces import ALL_KINDS, PieceKind


class SevenBag:
    """Deals pieces from shuffled bags that each contain all seven tetrominoes once.

    Compared with picking uniformly at random, the bag caps droughts: the
    longest possible wait for any piece is 12 draws, and the same piece can
    appear at most twice in a row (the end of one bag and the start of the next).
    """

    def __init__(self, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        self._queue: deque[PieceKind] = deque()

    def _refill(self) -> None:
        bag = list(ALL_KINDS)
        self._rng.shuffle(bag)
        self._queue.extend(bag)

    def next(self) -> PieceKind:
        """Remove and return the next piece."""
        if not self._queue:
            self._refill()
        return self._queue.popleft()

    def peek(self, count: int) -> list[PieceKind]:
        """Return the next ``count`` pieces without consuming them."""
        while len(self._queue) < count:
            self._refill()
        return list(self._queue)[:count]
