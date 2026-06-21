from ievr_bot.watchdog import Watchdog
from ievr_bot.states import GameState


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_timer_resets_on_state_change():
    clk = FakeClock()
    wd = Watchdog(stuck_seconds=10, now=clk)
    wd.update(GameState.IN_MATCH)
    clk.t = 5
    assert wd.seconds_in_state() == 5
    wd.update(GameState.HALFTIME)  # change resets
    assert wd.seconds_in_state() == 0


def test_is_stuck_after_threshold():
    clk = FakeClock()
    wd = Watchdog(stuck_seconds=10, now=clk)
    wd.update(GameState.UNKNOWN)
    clk.t = 9
    assert not wd.is_stuck()
    clk.t = 11
    assert wd.is_stuck()


def test_recovery_counter():
    wd = Watchdog(stuck_seconds=10)
    wd.note_recovery()
    wd.note_recovery()
    assert wd.consecutive_recoveries == 2
    wd.reset_recoveries()
    assert wd.consecutive_recoveries == 0
