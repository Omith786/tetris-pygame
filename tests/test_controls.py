import pytest

from tetris.controls import LEFT, RIGHT, AutoShift


def test_press_moves_immediately_then_waits_for_das() -> None:
    shift = AutoShift(das=0.15, arr=0.05)
    assert shift.press(RIGHT) == RIGHT
    assert shift.update(0.1) == 0
    assert shift.update(0.06) == 1  # DAS charged: first repeat
    assert shift.update(0.03) == 0
    assert shift.update(0.02) == 1
    assert shift.update(0.2) == 4


def test_release_stops_movement() -> None:
    shift = AutoShift(das=0.1, arr=0.05)
    shift.press(LEFT)
    shift.release(LEFT)
    assert shift.direction == 0
    assert shift.update(1.0) == 0


def test_most_recent_direction_wins_and_the_other_resumes_after_release() -> None:
    shift = AutoShift(das=0.1, arr=0.05)
    shift.press(LEFT)
    shift.update(0.3)
    shift.press(RIGHT)
    assert shift.direction == RIGHT
    assert shift.update(0.12) == 1
    shift.release(RIGHT)
    assert shift.direction == LEFT
    # Left must charge DAS again rather than snapping instantly.
    assert shift.update(0.05) == 0
    assert shift.update(0.06) == -1


def test_releasing_the_inactive_key_keeps_the_charge() -> None:
    shift = AutoShift(das=0.1, arr=0.05)
    shift.press(LEFT)
    shift.press(RIGHT)
    shift.update(0.09)
    shift.release(LEFT)
    assert shift.update(0.02) == 1


def test_clear_forgets_held_keys() -> None:
    shift = AutoShift()
    shift.press(LEFT)
    shift.clear()
    assert shift.update(1.0) == 0


def test_invalid_timings_are_rejected() -> None:
    with pytest.raises(ValueError):
        AutoShift(arr=0)
