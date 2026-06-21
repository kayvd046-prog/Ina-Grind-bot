import time
from dataclasses import dataclass
from typing import Callable, Optional
import numpy as np
from .states import GameState
from .config import Profile
from .logger import get_logger


@dataclass
class StatusUpdate:
    state: GameState
    score: float
    action: str
    matches: int
    frame: Optional[np.ndarray] = None


class Orchestrator:
    def __init__(self, source, detector, machine, watchdog, profile: Profile,
                 dry_run: bool = False,
                 on_update: Optional[Callable[[StatusUpdate], None]] = None) -> None:
        self.source = source
        self.detector = detector
        self.machine = machine
        self.watchdog = watchdog
        self.profile = profile
        self.dry_run = dry_run
        self.on_update = on_update
        self.log = get_logger()

    def step(self) -> StatusUpdate:
        frame = self.source.grab()
        state, score = self.detector.best_score(frame)
        self.watchdog.update(state)

        if self.watchdog.is_stuck():
            self.watchdog.note_recovery()
            action = "recovery: stuck, pressing cancel"
            if not self.dry_run:
                self.machine.controller.press("cancel")
            self.log.warning(action)
        elif self.dry_run:
            action = f"dry-run: would handle {state.name.lower()}"
        else:
            action = self.machine.handle(state)

        upd = StatusUpdate(state=state, score=score, action=action,
                           matches=self.machine.matches_completed, frame=frame)
        if self.on_update:
            self.on_update(upd)
        return upd

    def run(self, stop_event) -> None:
        interval = float(self.profile.timings.get("poll_interval", 0.4))
        self.log.info("Bot started (profile=%s, dry_run=%s)",
                      self.profile.name, self.dry_run)
        while not stop_event.is_set():
            try:
                self.step()
            except Exception:  # never let the unattended loop die
                self.log.exception("Error in step; backing off")
                time.sleep(float(self.profile.timings.get("recovery_backoff", 2.0)))
            time.sleep(interval)
        self.log.info("Bot stopped")


def build_orchestrator(profile: Profile, controller_kind: str = "vgamepad",
                       dry_run: bool = False, source=None,
                       on_update=None) -> "Orchestrator":
    from .capture import ScreenCapture, WindowCapture
    from .vision import StateDetector
    from .controller import make_controller
    from .statemachine import StateMachine
    from .watchdog import Watchdog

    if source is not None:
        src = source
    elif profile.capture_backend == "window":
        src = WindowCapture(profile.window_title)
    else:
        src = ScreenCapture()
    detector = StateDetector(profile.templates_dir, profile.match_threshold)
    kind = "null" if dry_run else controller_kind
    controller = make_controller(kind, profile.button_map)
    machine = StateMachine(profile, controller)
    watchdog = Watchdog(float(profile.timings.get("stuck_seconds", 25)))
    return Orchestrator(src, detector, machine, watchdog, profile,
                        dry_run=dry_run, on_update=on_update)
