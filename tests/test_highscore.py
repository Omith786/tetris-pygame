from pathlib import Path

from tetris.highscore import HighScoreTable, ScoreEntry


def entry(score: int) -> ScoreEntry:
    return ScoreEntry(score, lines=score // 100, level=1, date="2026-01-01")


def test_missing_file_is_an_empty_table(tmp_path: Path) -> None:
    table = HighScoreTable.load(tmp_path / "nope.json")
    assert table.entries == []
    assert table.best == 0


def test_corrupt_file_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "scores.json"
    path.write_text("{not json", encoding="utf-8")
    assert HighScoreTable.load(path).entries == []
    path.write_text('[{"score": "x"}]', encoding="utf-8")
    assert HighScoreTable.load(path).entries == []


def test_round_trip_keeps_order(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "scores.json"
    table = HighScoreTable(path)
    for score in (300, 900, 100):
        table.add(entry(score))
    table.save()
    loaded = HighScoreTable.load(path)
    assert [e.score for e in loaded.entries] == [900, 300, 100]
    assert loaded.best == 900
    assert not list(path.parent.glob("*.tmp"))


def test_table_is_capped_and_reports_rank(tmp_path: Path) -> None:
    table = HighScoreTable(tmp_path / "s.json", max_entries=3)
    assert [table.add(entry(s)) for s in (500, 400, 300)] == [1, 2, 3]
    assert not table.qualifies(200)
    assert table.add(entry(200)) is None
    assert table.add(entry(450)) == 2
    assert [e.score for e in table.entries] == [500, 450, 400]


def test_ties_rank_below_the_existing_score(tmp_path: Path) -> None:
    table = HighScoreTable(tmp_path / "s.json")
    table.add(entry(500))
    assert table.add(entry(500)) == 2


def test_zero_never_qualifies(tmp_path: Path) -> None:
    assert not HighScoreTable(tmp_path / "s.json").qualifies(0)
