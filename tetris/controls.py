"""Delayed auto shift (DAS) and auto repeat rate (ARR) for sideways movement.

Holding left or right should move the piece once, pause briefly, then slide at a
steady rate. Relying on the operating system's key repeat instead gives laggy,
machine-dependent movement, so the timing lives here, independent of pygame.
"""

from __future__ import annotations

LEFT = -1
RIGHT = 1


class AutoShift:
    """Turns held-direction state into a stream of single-column steps.

    When both directions are held, the most recently pressed one wins, which
    is how most modern games resolve the conflict and feels the least sticky.
    """

    def __init__(self, das: float = 0.167, arr: float = 0.033) -> None:
        if das < 0 or arr <= 0:
            raise ValueError("das must be >= 0 and arr must be > 0")
        self.das = das
        self.arr = arr
        self._held: list[int] = []
        self._elapsed = 0.0
        self._repeats = 0

    @property
    def direction(self) -> int:
        """The direction currently in control (0 if nothing is held)."""
        return self._held[-1] if self._held else 0

    def press(self, direction: int) -> int:
        """Register a key press and return the immediate step (the direction itself)."""
        if direction in self._held:
            self._held.remove(direction)
        self._held.append(direction)
        self._restart()
        return direction

    def release(self, direction: int) -> None:
        was_active = self.direction == direction
        if direction in self._held:
            self._held.remove(direction)
        if was_active:
            # The other key (if still held) takes over and must charge DAS afresh.
            self._restart()

    def clear(self) -> None:
        """Forget all held keys, e.g. when the game pauses."""
        self._held.clear()
        self._restart()

    def update(self, dt: float) -> int:
        """Advance time and return the signed number of extra steps to apply."""
        if not self._held:
            return 0
        self._elapsed += dt
        if self._elapsed < self.das:
            return 0
        # The first repeat fires as soon as DAS has charged, then one every ARR.
        total = int((self._elapsed - self.das) / self.arr) + 1
        steps = total - self._repeats
        self._repeats = total
        return steps * self.direction

    def _restart(self) -> None:
        self._elapsed = 0.0
        self._repeats = 0
