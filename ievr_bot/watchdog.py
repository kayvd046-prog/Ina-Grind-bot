import time
from typing import Callable
from .states import GameState


class Watchdog:
    def __init__(self, stuck_seconds: float,
                 now: Callable[[], float] = time.monotonic) -> None:
        self.stuck_seconds = stuck_seconds
        self._now = now
        self._state: GameState | None = None
        self._since = now()
        self.consecutive_recoveries = 0

    def update(self, state: GameState) -> None:
        if state != self._state:
            self._state = state
            self._since = self._now()

    def seconds_in_state(self) -> float:
        return self._now() - self._since

    def is_stuck(self) -> bool:
        return self.seconds_in_state() >= self.stuck_seconds

    def note_recovery(self) -> None:
        self.consecutive_recoveries += 1

    def reset_recoveries(self) -> None:
        self.consecutive_recoveries = 0
