"""Session statistics derived from the match counter.

Pure bookkeeping: the GUI feeds it the current ``matches_completed`` on every
status update; elapsed time runs from the first update to the most recent one,
so the numbers freeze when the bot stops.
"""
import time
from typing import Callable


class SessionStats:
    def __init__(self, now: Callable[[], float] = time.monotonic) -> None:
        self._now = now
        self.reset()

    def reset(self) -> None:
        self._t0 = None
        self._elapsed = 0.0
        self.matches = 0

    def note_matches(self, n: int) -> None:
        t = self._now()
        if self._t0 is None:
            self._t0 = t
        self._elapsed = t - self._t0
        self.matches = int(n)

    def matches_per_hour(self) -> float:
        if self.matches <= 0 or self._elapsed <= 0:
            return 0.0
        return self.matches / self._elapsed * 3600.0

    def avg_match_seconds(self) -> float:
        if self.matches <= 0:
            return 0.0
        return self._elapsed / self.matches

    def format_summary(self) -> str:
        if self.matches <= 0:
            return "—"
        avg = self.avg_match_seconds()
        return (f"{self.matches_per_hour():.1f}/h · "
                f"avg {int(avg // 60)}m {int(avg % 60):02d}s")
