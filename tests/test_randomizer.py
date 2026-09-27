from tetris.pieces import ALL_KINDS
from tetris.randomizer import SevenBag


def test_each_bag_contains_every_piece_once() -> None:
    bag = SevenBag(seed=42)
    for _ in range(20):
        dealt = [bag.next() for _ in range(7)]
        assert sorted(dealt) == sorted(ALL_KINDS)


def test_peek_does_not_consume() -> None:
    bag = SevenBag(seed=1)
    preview = bag.peek(10)
    assert len(preview) == 10
    assert [bag.next() for _ in range(10)] == preview


def test_same_seed_gives_same_sequence() -> None:
    a, b = SevenBag(seed=7), SevenBag(seed=7)
    assert [a.next() for _ in range(50)] == [b.next() for _ in range(50)]


def test_no_piece_waits_longer_than_twelve_draws() -> None:
    bag = SevenBag(seed=3)
    sequence = [bag.next() for _ in range(7 * 200)]
    for kind in ALL_KINDS:
        positions = [i for i, k in enumerate(sequence) if k is kind]
        gaps = [b - a for a, b in zip(positions, positions[1:])]
        assert max(gaps) <= 13  # at most 12 other pieces in between
