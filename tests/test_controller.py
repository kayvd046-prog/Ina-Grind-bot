import pytest
from ievr_bot.controller import NullController, make_controller


def test_null_controller_records_presses():
    c = NullController()
    c.press("confirm")
    c.press("commander_toggle", duration=0.2)
    assert c.presses == ["confirm", "commander_toggle"]


def test_make_controller_null():
    c = make_controller("null", {"confirm": "A"})
    assert isinstance(c, NullController)


def test_make_controller_unknown_kind():
    with pytest.raises(ValueError):
        make_controller("bogus", {})
