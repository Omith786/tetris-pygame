import pytest

from tetris.mechanics import TSpin
from tetris.scoring import (
    ClassicScoring,
    ClearContext,
    GuidelineScoring,
    describe_clear,
    gravity_interval,
    is_difficult,
    level_for_lines,
)

guideline = GuidelineScoring()


def ctx(lines: int, tspin: TSpin = TSpin.NONE, level: int = 1, combo: int = 0, b2b: bool = False) -> ClearContext:
    return ClearContext(lines, tspin, level, combo, b2b)


@pytest.mark.parametrize(("lines", "points"), [(1, 100), (2, 300), (3, 500), (4, 800)])
def test_guideline_line_values(lines: int, points: int) -> None:
    assert guideline.clear_points(ctx(lines)) == points


@pytest.mark.parametrize(
    ("lines", "tspin", "points"),
    [
        (0, TSpin.FULL, 400),
        (1, TSpin.FULL, 800),
        (2, TSpin.FULL, 1200),
        (3, TSpin.FULL, 1600),
        (0, TSpin.MINI, 100),
        (1, TSpin.MINI, 200),
        (2, TSpin.MINI, 400),
    ],
)
def test_guideline_tspin_values(lines: int, tspin: TSpin, points: int) -> None:
    assert guideline.clear_points(ctx(lines, tspin)) == points


def test_points_scale_with_level() -> None:
    assert guideline.clear_points(ctx(4, level=5)) == 4000


def test_back_to_back_bonus_applies_only_to_difficult_clears() -> None:
    assert guideline.clear_points(ctx(4, b2b=True)) == 1200
    assert guideline.clear_points(ctx(2, TSpin.FULL, b2b=True)) == 1800
    # A single can never be a back-to-back clear, even if the flag is set.
    assert guideline.clear_points(ctx(1, b2b=True)) == 100


def test_combo_bonus() -> None:
    assert guideline.clear_points(ctx(1, combo=3, level=2)) == 100 * 2 + 50 * 3 * 2


def test_drop_points() -> None:
    assert guideline.soft_drop_points(7) == 7
    assert guideline.hard_drop_points(7) == 14


def test_classic_rules_ignore_spins_and_bonuses() -> None:
    classic = ClassicScoring()
    assert classic.clear_points(ctx(4, level=3)) == 3600
    assert classic.clear_points(ctx(1, TSpin.FULL, combo=5, b2b=True)) == 40
    assert classic.hard_drop_points(10) == 10


def test_difficulty_classification() -> None:
    assert is_difficult(4, TSpin.NONE)
    assert is_difficult(1, TSpin.MINI)
    assert not is_difficult(3, TSpin.NONE)
    assert not is_difficult(0, TSpin.FULL)


def test_level_progression() -> None:
    assert level_for_lines(0) == 1
    assert level_for_lines(9) == 1
    assert level_for_lines(10) == 2
    assert level_for_lines(25, start_level=5) == 7


def test_gravity_curve_speeds_up_and_is_capped() -> None:
    assert gravity_interval(1) == pytest.approx(1.0)
    assert gravity_interval(2) == pytest.approx(0.793)
    intervals = [gravity_interval(level) for level in range(1, 21)]
    assert all(a > b for a, b in zip(intervals, intervals[1:]))
    assert gravity_interval(50) == gravity_interval(20)
    assert gravity_interval(0) == gravity_interval(1)


def test_clear_descriptions() -> None:
    assert describe_clear(4, TSpin.NONE) == "TETRIS"
    assert describe_clear(2, TSpin.FULL) == "T-SPIN DOUBLE"
    assert describe_clear(1, TSpin.MINI) == "T-SPIN MINI SINGLE"
    assert describe_clear(0, TSpin.FULL) == "T-SPIN"
