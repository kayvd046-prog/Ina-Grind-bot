from ievr_bot.statemachine import StateMachine
from ievr_bot.controller import NullController
from ievr_bot.config import Profile
from ievr_bot.states import GameState
from pathlib import Path


def _profile():
    return Profile(
        name="t", mode="pve", templates_dir=Path("."),
        button_map={"confirm": "A", "cancel": "B",
                    "commander_toggle": "Y", "menu": "START"},
        timings={}, match_threshold=0.85, phase2_enabled=False,
    )


def test_kickoff_enables_commander_mode():
    c = NullController()
    sm = StateMachine(_profile(), c)
    sm.handle(GameState.KICKOFF)
    assert "commander_toggle" in c.presses


def test_terminal_screen_presses_confirm():
    c = NullController()
    sm = StateMachine(_profile(), c)
    sm.handle(GameState.REWARDS)
    assert c.presses == ["confirm"]


def test_in_match_sends_no_input():
    c = NullController()
    sm = StateMachine(_profile(), c)
    sm.handle(GameState.IN_MATCH)
    assert c.presses == []


def test_error_dialog_presses_cancel():
    c = NullController()
    sm = StateMachine(_profile(), c)
    sm.handle(GameState.ERROR_DIALOG)
    assert c.presses == ["cancel"]


def test_post_match_increments_counter():
    c = NullController()
    sm = StateMachine(_profile(), c)
    assert sm.matches_completed == 0
    sm.handle(GameState.POST_MATCH)
    assert sm.matches_completed == 1


def test_rematch_presses_confirm():
    c = NullController()
    sm = StateMachine(_profile(), c)
    msg = sm.handle(GameState.REMATCH)
    assert c.presses == ["confirm"]
    assert "rematch" in msg.lower()


def test_rematch_does_not_double_count_matches():
    # POST_MATCH already counts the finished match; the rematch prompt only
    # starts the next one, so it must not increment the counter again.
    c = NullController()
    sm = StateMachine(_profile(), c)
    sm.handle(GameState.POST_MATCH)
    sm.handle(GameState.REMATCH)
    assert sm.matches_completed == 1
