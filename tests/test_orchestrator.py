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


# --- stop conditions -------------------------------------------------------

def _never_set_event():
    import threading
    return threading.Event()


def test_run_stops_after_n_matches():
    p = _profile()
    c = NullController()
    src = StaticFrameSource(np.zeros((20, 20, 3), np.uint8))
    sm = StateMachine(p, c)
    wd = Watchdog(stuck_seconds=10, now=lambda: 0.0)
    # Every REMATCH step counts one finished match, so 2 steps reach the limit.
    o = Orchestrator(src, FakeDetector(GameState.REMATCH), sm, wd, p,
                     stop_after_matches=2)
    o.run(_never_set_event())  # must return on its own
    assert sm.matches_completed == 2


def test_run_stops_after_time_limit():
    p = _profile()
    src = StaticFrameSource(np.zeros((20, 20, 3), np.uint8))
    sm = StateMachine(p, NullController())
    wd = Watchdog(stuck_seconds=10, now=lambda: 0.0)
    o = Orchestrator(src, FakeDetector(GameState.IN_MATCH), sm, wd, p,
                     stop_after_seconds=0.0)
    o.run(_never_set_event())  # limit already elapsed -> returns immediately
    assert True


def test_run_without_limits_still_honours_stop_event():
    import threading
    p = _profile()
    src = StaticFrameSource(np.zeros((20, 20, 3), np.uint8))
    sm = StateMachine(p, NullController())
    wd = Watchdog(stuck_seconds=10, now=lambda: 0.0)
    o = Orchestrator(src, FakeDetector(GameState.IN_MATCH), sm, wd, p)
    ev = threading.Event()
    ev.set()
    o.run(ev)
    assert True


# --- keep-awake wiring -----------------------------------------------------

class FakeKeepAwake:
    def __init__(self):
        self.active = None

    def activate(self):
        self.active = True

    def deactivate(self):
        self.active = False


def test_run_activates_and_deactivates_keep_awake():
    import threading
    p = _profile()
    src = StaticFrameSource(np.zeros((20, 20, 3), np.uint8))
    sm = StateMachine(p, NullController())
    wd = Watchdog(stuck_seconds=10, now=lambda: 0.0)
    ka = FakeKeepAwake()
    o = Orchestrator(src, FakeDetector(GameState.IN_MATCH), sm, wd, p,
                     keep_awake=ka)
    ev = threading.Event()
    ev.set()
    o.run(ev)
    assert ka.active is False  # activated during run, released afterwards


# --- stuck reporter wiring -------------------------------------------------

class StuckNow:
    """Watchdog clock that reports far beyond stuck_seconds."""

    def __call__(self):
        return 0.0


class RecordingReporter:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def report(self, frame, state, score):
        if self.fail:
            raise OSError("disk full")
        self.calls.append((state, score))
        return None


def _stuck_orch(reporter):
    p = _profile()
    src = StaticFrameSource(np.zeros((20, 20, 3), np.uint8))
    sm = StateMachine(p, NullController())
    t = iter([0.0, 100.0, 200.0, 300.0, 400.0, 500.0])
    wd = Watchdog(stuck_seconds=10, now=lambda: next(t))
    return Orchestrator(src, FakeDetector(GameState.UNKNOWN), sm, wd, p,
                        stuck_reporter=reporter)


def test_stuck_recovery_saves_a_diagnosis():
    rep = RecordingReporter()
    o = _stuck_orch(rep)
    o.step()  # watchdog sees UNKNOWN for 100s -> stuck -> report
    assert rep.calls == [(GameState.UNKNOWN, 0.99)]


class RecordingTracker:
    def __init__(self):
        self.observed = 0
        self.flushes = 0
        self.totals = {"Fire Pinwheel": 2}
        self.matches = 0

    def observe_frame(self, frame):
        self.observed += 1

    def flush_match(self):
        self.flushes += 1
        self.matches += 1


def test_rewards_observed_on_end_screen_transitions_and_flushed_on_rematch():
    p = _profile()
    src = StaticFrameSource(np.zeros((20, 20, 3), np.uint8))
    sm = StateMachine(p, NullController())
    wd = Watchdog(stuck_seconds=1000, now=lambda: 0.0)
    tracker = RecordingTracker()
    seen = []
    seq = [GameState.IN_MATCH, GameState.REWARDS, GameState.REWARDS,
           GameState.POST_MATCH, GameState.REMATCH]
    o = Orchestrator(src, ScriptedDetector(seq), sm, wd, p,
                     rewards_tracker=tracker,
                     on_rewards=lambda totals, n: seen.append((totals, n)))
    for _ in seq:
        o.step()
    # One observation per transition into an end screen (REWARDS, POST_MATCH,
    # REMATCH) — not one per poll (REWARDS is polled twice).
    assert tracker.observed == 3
    assert tracker.flushes == 1
    assert seen == [({"Fire Pinwheel": 2}, 1)]


def test_rewards_tracker_failure_never_breaks_the_loop():
    class BrokenTracker(RecordingTracker):
        def observe_frame(self, frame):
            raise OSError("ocr exploded")

    p = _profile()
    src = StaticFrameSource(np.zeros((20, 20, 3), np.uint8))
    sm = StateMachine(p, NullController())
    wd = Watchdog(stuck_seconds=1000, now=lambda: 0.0)
    o = Orchestrator(src, FakeDetector(GameState.REWARDS), sm, wd, p,
                     rewards_tracker=BrokenTracker())
    upd = o.step()  # must not raise
    assert upd.state == GameState.REWARDS


def test_stuck_reporter_failure_never_breaks_the_loop():
    o = _stuck_orch(RecordingReporter(fail=True))
    upd = o.step()  # must not raise even though the reporter does
    assert "recovery" in upd.action
