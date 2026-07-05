import numpy as np
from pathlib import Path
from ievr_bot.orchestrator import Orchestrator
from ievr_bot.capture import StaticFrameSource
from ievr_bot.statemachine import StateMachine
from ievr_bot.controller import NullController
from ievr_bot.watchdog import Watchdog
from ievr_bot.config import Profile
from ievr_bot.states import GameState


class FakeDetector:
    def __init__(self, state):
        self.state = state

    def best_score(self, frame):
        return (self.state, 0.99)


def _profile():
    return Profile(name="t", mode="pve", templates_dir=Path("."),
                   button_map={"confirm": "A", "cancel": "B",
                               "commander_toggle": "Y", "menu": "START"},
                   timings={"poll_interval": 0.0, "stuck_seconds": 10},
                   match_threshold=0.85, phase2_enabled=False)


def _orch(state, dry_run=False):
    p = _profile()
    c = NullController()
    src = StaticFrameSource(np.zeros((20, 20, 3), np.uint8))
    sm = StateMachine(p, c)
    wd = Watchdog(stuck_seconds=10, now=lambda: 0.0)
    o = Orchestrator(src, FakeDetector(state), sm, wd, p, dry_run=dry_run)
    return o, c


def test_step_returns_status_and_acts():
    o, c = _orch(GameState.KICKOFF)
    upd = o.step()
    assert upd.state == GameState.KICKOFF
    assert "commander_toggle" in c.presses
    assert upd.score == 0.99


def test_dry_run_sends_no_input():
    o, c = _orch(GameState.KICKOFF, dry_run=True)
    o.step()
    assert c.presses == []


class ScriptedDetector:
    """Returns a fixed sequence of states, one per step."""
    def __init__(self, states):
        self.states = list(states)
        self.i = 0

    def best_score(self, frame):
        s = self.states[min(self.i, len(self.states) - 1)]
        self.i += 1
        return (s, 0.99)


def test_full_match_loop_including_rematch():
    p = _profile()
    c = NullController()
    src = StaticFrameSource(np.zeros((20, 20, 3), np.uint8))
    sm = StateMachine(p, c)
    wd = Watchdog(stuck_seconds=10, now=lambda: 0.0)
    seq = [GameState.MAIN_MENU, GameState.LOADING, GameState.KICKOFF,
           GameState.IN_MATCH, GameState.GOAL, GameState.FULLTIME,
           GameState.REWARDS, GameState.POST_MATCH, GameState.REMATCH]
    o = Orchestrator(src, ScriptedDetector(seq), sm, wd, p)
    for _ in seq:
        o.step()
    # The finished match is counted once (at POST_MATCH); REMATCH only starts
    # the next one and must confirm without re-counting.
    assert sm.matches_completed == 1
    assert c.presses[-1] == "confirm"
    # IN_MATCH / LOADING send no input; KICKOFF enables commander mode.
    assert "commander_toggle" in c.presses


def test_step_logs_state_transitions_only(caplog):
    import logging
    p = _profile()
    c = NullController()
    src = StaticFrameSource(np.zeros((20, 20, 3), np.uint8))
    sm = StateMachine(p, c)
    wd = Watchdog(stuck_seconds=10, now=lambda: 0.0)
    seq = [GameState.IN_MATCH, GameState.IN_MATCH, GameState.POST_MATCH,
           GameState.POST_MATCH, GameState.REMATCH]
    o = Orchestrator(src, ScriptedDetector(seq), sm, wd, p)
    with caplog.at_level(logging.INFO, logger="ievr"):
        for _ in seq:
            o.step()
    transitions = [r.message for r in caplog.records if "state ->" in r.message]
    # One line per state CHANGE (3 changes), not one per poll (5 polls).
    assert len(transitions) == 3
    assert "POST_MATCH" in transitions[1] and "REMATCH" in transitions[2]


def test_on_update_callback_called():
    p = _profile()
    src = StaticFrameSource(np.zeros((20, 20, 3), np.uint8))
    sm = StateMachine(p, NullController())
    wd = Watchdog(stuck_seconds=10, now=lambda: 0.0)
    seen = []
    o = Orchestrator(src, FakeDetector(GameState.IN_MATCH), sm, wd, p,
                     on_update=seen.append)
    o.step()
    assert len(seen) == 1 and seen[0].state == GameState.IN_MATCH
