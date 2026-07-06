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
                 on_update: Optional[Callable[[StatusUpdate], None]] = None,
                 stop_after_matches: Optional[int] = None,
                 stop_after_seconds: Optional[float] = None,
                 keep_awake=None, stuck_reporter=None,
                 rewards_tracker=None, on_rewards=None) -> None:
        self.source = source
        self.detector = detector
        self.machine = machine
        self.watchdog = watchdog
        self.profile = profile
        self.dry_run = dry_run
        self.on_update = on_update
        self.stop_after_matches = stop_after_matches
        self.stop_after_seconds = stop_after_seconds
        self.keep_awake = keep_awake
        self.stuck_reporter = stuck_reporter
        self.rewards_tracker = rewards_tracker
        self.on_rewards = on_rewards
        self.log = get_logger()
        self._last_logged_state: Optional[GameState] = None

    def step(self) -> StatusUpdate:
        frame = self.source.grab()
        state, score = self.detector.best_score(frame)
        transition = state != self._last_logged_state
        prev_matches = self.machine.matches_completed
        self.watchdog.update(state)

        if self.watchdog.is_stuck():
            self.watchdog.note_recovery()
            action = "recovery: stuck, pressing cancel"
            if not self.dry_run:
                self.machine.controller.press("cancel")
            self.log.warning(action)
            if self.stuck_reporter is not None:
                try:
                    saved = self.stuck_reporter.report(frame, state, score)
                    if saved is not None:
                        self.log.warning("saved stuck-screen diagnosis -> %s",
                                         saved)
                except Exception:
                    self.log.exception("could not save stuck-screen diagnosis")
        elif self.dry_run:
            action = f"dry-run: would handle {state.name.lower()}"
        else:
            action = self.machine.handle(state)

        if self.rewards_tracker is not None:
            try:
                from .rewards import REWARD_SCREENS
                # OCR only on the transition onto an end screen, not every poll.
                if transition and state in REWARD_SCREENS:
                    self.rewards_tracker.observe_frame(frame)
                if self.machine.matches_completed > prev_matches:
                    self.rewards_tracker.flush_match()
                    if self.on_rewards is not None:
                        self.on_rewards(dict(self.rewards_tracker.totals),
                                        self.rewards_tracker.matches)
            except Exception:
                self.log.exception("rewards tracking failed")

        # Log each state CHANGE (not every poll) so an unattended run leaves a
        # readable timeline in ievr.log for remote diagnosis.
        if state != self._last_logged_state:
            self.log.info("state -> %s (score %.2f): %s",
                          state.name, score, action)
            self._last_logged_state = state

        upd = StatusUpdate(state=state, score=score, action=action,
                           matches=self.machine.matches_completed, frame=frame)
        if self.on_update:
            self.on_update(upd)
        return upd

    def run(self, stop_event) -> None:
        interval = float(self.profile.timings.get("poll_interval", 0.4))
        self.log.info("Bot started (profile=%s, dry_run=%s)",
                      self.profile.name, self.dry_run)
        start = time.monotonic()
        last_err = None  # signature of the previous step error
        err_streak = 0   # how many times it has repeated in a row
        if self.keep_awake is not None:
            self.keep_awake.activate()
        try:
            while not stop_event.is_set():
                if (self.stop_after_seconds is not None
                        and time.monotonic() - start >= self.stop_after_seconds):
                    self.log.info(
                        "Time limit reached (%.1f h) — stopping after %d "
                        "match(es).", self.stop_after_seconds / 3600.0,
                        self.machine.matches_completed)
                    break
                try:
                    self.step()
                    last_err, err_streak = None, 0
                except Exception as exc:  # never let the unattended loop die
                    # Rate-limit identical repeated errors (e.g. window minimized
                    # for 30 min) so we don't write a stack trace every poll and
                    # fill disk.
                    sig = f"{type(exc).__name__}: {exc}"
                    if sig == last_err:
                        err_streak += 1
                        if err_streak % 50 == 0:
                            self.log.warning("Still failing (x%d): %s",
                                             err_streak, sig)
                    else:
                        self.log.exception("Error in step; backing off")
                        last_err, err_streak = sig, 1
                    time.sleep(float(
                        self.profile.timings.get("recovery_backoff", 2.0)))
                if (self.stop_after_matches
                        and self.machine.matches_completed >= self.stop_after_matches):
                    self.log.info("Match limit reached (%d) — stopping.",
                                  self.stop_after_matches)
                    break
                time.sleep(interval)
        finally:
            if self.keep_awake is not None:
                self.keep_awake.deactivate()
            self.log.info("Bot stopped")


def build_orchestrator(profile: Profile, controller_kind: str = "vgamepad",
                       dry_run: bool = False, source=None,
                       on_update=None, stop_after_matches=None,
                       stop_after_seconds=None, on_rewards=None) -> "Orchestrator":
    from .capture import build_frame_source
    from .composite_detector import build_detector
    from .controller import make_controller
    from .keepawake import KeepAwake
    from .paths import user_data_dir
    from .statemachine import StateMachine
    from .stuck_reporter import StuckReporter, find_ocr_engine
    from .watchdog import Watchdog

    src = source if source is not None else build_frame_source(profile)
    detector = build_detector(profile)
    kind = "null" if dry_run else controller_kind
    controller = make_controller(kind, profile.button_map)
    machine = StateMachine(profile, controller)
    watchdog = Watchdog(float(profile.timings.get("stuck_seconds", 25)))
    from .rewards import RewardsTracker
    engine = find_ocr_engine(detector)
    reporter = StuckReporter(user_data_dir() / "diag", ocr_engine=engine)
    tracker = RewardsTracker(ocr_engine=engine)
    return Orchestrator(src, detector, machine, watchdog, profile,
                        dry_run=dry_run, on_update=on_update,
                        stop_after_matches=stop_after_matches,
                        stop_after_seconds=stop_after_seconds,
                        keep_awake=KeepAwake(), stuck_reporter=reporter,
                        rewards_tracker=tracker, on_rewards=on_rewards)
