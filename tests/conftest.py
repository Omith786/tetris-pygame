"""Shared test helpers. Forces SDL's headless drivers before pygame is imported."""

from __future__ import annotations

import os
from collections import deque
from collections.abc import Iterable

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest  # noqa: E402

from tetris.board import Board  # noqa: E402
from tetris.game import Game, GameConfig  # noqa: E402
from tetris.pieces import PieceKind  # noqa: E402


class FixedPieces:
    """Deals a scripted sequence, then O pieces forever, so tests control every spawn."""

    def __init__(self, kinds: Iterable[PieceKind | str]) -> None:
        self._queue = deque(PieceKind(k) for k in kinds)

    def next(self) -> PieceKind:
        return self._queue.popleft() if self._queue else PieceKind.O

    def peek(self, count: int) -> list[PieceKind]:
        items = list(self._queue)[:count]
        return items + [PieceKind.O] * (count - len(items))


def make_game(
    kinds: str = "",
    rows: list[str] | None = None,
    **config: object,
) -> Game:
    """A game with scripted pieces, an optional prepared board and instant line clears by default."""
    config.setdefault("line_clear_delay", 0.0)
    board = Board.from_rows(rows) if rows else Board()
    return Game(GameConfig(**config), board=board, pieces=FixedPieces(kinds))  # type: ignore[arg-type]


@pytest.fixture
def empty_board() -> Board:
    return Board()
