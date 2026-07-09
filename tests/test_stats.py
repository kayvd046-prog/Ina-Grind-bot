"""Session statistics: matches per hour and average match duration."""
from ievr_bot.stats import SessionStats


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_no_matches_yet_formats_as_dash():
    s = SessionStats(now=FakeClock())
    s.note_matches(0)
    assert s.format_summary() == "—"


def test_rate_and_average_after_matches():
    clock = FakeClock()
    s = SessionStats(now=clock)
    s.note_matches(0)          # session starts at t=0
    clock.t = 1800.0
    s.note_matches(1)          # one match in 30 minutes
    assert s.matches_per_hour() == 2.0
    assert s.avg_match_seconds() == 1800.0
    assert s.format_summary() == "2.0/h · avg 30m 00s"


def test_rate_updates_with_more_matches():
    clock = FakeClock()
    s = SessionStats(now=clock)
    s.note_matches(0)
    clock.t = 3600.0
    s.note_matches(4)
    assert s.matches_per_hour() == 4.0
    assert s.avg_match_seconds() == 900.0
    assert "4.0/h" in s.format_summary()
    assert "15m 00s" in s.format_summary()


def test_reset_starts_a_new_session():
    clock = FakeClock()
    s = SessionStats(now=clock)
    s.note_matches(0)
    clock.t = 100.0
    s.note_matches(2)
    s.reset()
    assert s.matches == 0
    assert s.format_summary() == "—"


def test_average_under_a_minute_shows_seconds():
    clock = FakeClock()
    s = SessionStats(now=clock)
    s.note_matches(0)
    clock.t = 45.0
    s.note_matches(1)
    assert "0m 45s" in s.format_summary()
