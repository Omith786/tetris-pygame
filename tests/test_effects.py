from tetris.effects import Effects, clear_callout
from tetris.game import ClearEvent, LevelUpEvent, LockEvent
from tetris.mechanics import TSpin
from tetris.pieces import PieceKind


def test_callout_lists_bonuses() -> None:
    event = ClearEvent(rows=(20, 21), lines=2, tspin=TSpin.FULL, back_to_back=True, combo=2, points=1900)
    assert clear_callout(event) == ("BACK-TO-BACK", "T-SPIN DOUBLE", "COMBO x2", "+1900")


def test_effects_expire() -> None:
    effects = Effects()
    effects.handle([LockEvent(((0, 21),), PieceKind.O), LevelUpEvent(3)])
    assert len(effects.flashes) == 1
    assert effects.popups[0].lines == ("LEVEL 3",)
    effects.update(0.5)
    assert effects.flashes == []
    assert effects.popups and 0 < effects.popups[0].alpha <= 1
    effects.update(2.0)
    assert effects.popups == []
