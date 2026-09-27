"""Persistent local high-score table stored as JSON."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

DEFAULT_PATH = Path(os.environ.get("TETRIS_HIGHSCORE_PATH", Path(__file__).resolve().parent.parent / "highscores.json"))
MAX_ENTRIES = 5


@dataclass(frozen=True, slots=True)
class ScoreEntry:
    score: int
    lines: int
    level: int
    date: str

    @classmethod
    def today(cls, score: int, lines: int, level: int) -> ScoreEntry:
        return cls(score, lines, level, date.today().isoformat())


class HighScoreTable:
    """The best ``max_entries`` scores, highest first.

    A missing or unreadable file is treated as an empty table rather than an
    error: losing a leaderboard should never stop the game from starting.
    """

    def __init__(self, path: Path | str = DEFAULT_PATH, max_entries: int = MAX_ENTRIES) -> None:
        self.path = Path(path)
        self.max_entries = max_entries
        self.entries: list[ScoreEntry] = []

    @classmethod
    def load(cls, path: Path | str = DEFAULT_PATH, max_entries: int = MAX_ENTRIES) -> HighScoreTable:
        table = cls(path, max_entries)
        try:
            raw = json.loads(table.path.read_text(encoding="utf-8"))
            entries = [ScoreEntry(int(e["score"]), int(e["lines"]), int(e["level"]), str(e["date"])) for e in raw]
        except (OSError, ValueError, TypeError, KeyError):
            entries = []
        table.entries = sorted(entries, key=lambda e: e.score, reverse=True)[:max_entries]
        return table

    @property
    def best(self) -> int:
        return self.entries[0].score if self.entries else 0

    def qualifies(self, score: int) -> bool:
        """Whether ``score`` would earn a place on the table."""
        if score <= 0:
            return False
        return len(self.entries) < self.max_entries or score > self.entries[-1].score

    def add(self, entry: ScoreEntry) -> int | None:
        """Insert an entry, returning its 1-based rank, or ``None`` if it did not place."""
        if not self.qualifies(entry.score):
            return None
        # Ties go below existing entries: the earlier achievement keeps its place.
        rank = next((i for i, e in enumerate(self.entries) if entry.score > e.score), len(self.entries))
        self.entries.insert(rank, entry)
        del self.entries[self.max_entries :]
        return rank + 1

    def save(self) -> None:
        """Write atomically so a crash mid-save cannot corrupt the existing table."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps([asdict(e) for e in self.entries], indent=2)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".highscores-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
            os.replace(tmp, self.path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
