"""Short-lived visual feedback derived from game events (callouts and flashes).

Kept free of pygame so the timing is testable; the renderer only reads it.
"""

from __future__ import annotations

from dataclasses import dataclass

from tetris.game import ClearEvent, GameEvent, LevelUpEvent, LockEvent
from tetris.pieces import Cell
from tetris.scoring import describe_clear

POPUP_SECONDS = 1.4
LOCK_FLASH_SECONDS = 0.18


@dataclass(slots=True)
class Popup:
    lines: tuple[str, ...]
    ttl: float
    duration: float = POPUP_SECONDS

    @property
    def alpha(self) -> float:
        """Opacity from 1 down to 0; holds full strength for the first half."""
        return max(0.0, min(1.0, 2 * self.ttl / self.duration))

    @property
    def rise(self) -> float:
        """How far (0-1) the popup has drifted upwards."""
        return 1.0 - self.ttl / self.duration


@dataclass(slots=True)
class Flash:
    cells: tuple[Cell, ...]
    ttl: float

    @property
    def strength(self) -> float:
        return max(0.0, self.ttl / LOCK_FLASH_SECONDS)


class Effects:
    """Collects popups and lock flashes and ages them each frame."""

    def __init__(self) -> None:
        self.popups: list[Popup] = []
        self.flashes: list[Flash] = []

    def clear(self) -> None:
        self.popups.clear()
        self.flashes.clear()

    def handle(self, events: list[GameEvent]) -> None:
        for event in events:
            if isinstance(event, LockEvent):
                self.flashes.append(Flash(event.cells, LOCK_FLASH_SECONDS))
            elif isinstance(event, ClearEvent):
                self.popups.append(Popup(clear_callout(event), POPUP_SECONDS))
            elif isinstance(event, LevelUpEvent):
                self.popups.append(Popup((f"LEVEL {event.level}",), POPUP_SECONDS))

    def update(self, dt: float) -> None:
        for popup in self.popups:
            popup.ttl -= dt
        for flash in self.flashes:
            flash.ttl -= dt
        self.popups = [p for p in self.popups if p.ttl > 0]
        self.flashes = [f for f in self.flashes if f.ttl > 0]


def clear_callout(event: ClearEvent) -> tuple[str, ...]:
    """The text lines shown for a scoring lock, e.g. ``("BACK-TO-BACK", "TETRIS", "+1200")``."""
    lines: list[str] = []
    if event.back_to_back:
        lines.append("BACK-TO-BACK")
    lines.append(describe_clear(event.lines, event.tspin))
    if event.combo > 0:
        lines.append(f"COMBO x{event.combo}")
    lines.append(f"+{event.points}")
    return tuple(lines)
