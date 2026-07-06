import threading
from PySide6.QtCore import QThread, Signal
from ievr_bot.orchestrator import build_orchestrator
from ievr_bot.logger import get_logger


class BotWorker(QThread):
    status = Signal(object)
    log_line = Signal(str)
    stopped = Signal()

    def __init__(self, profile, controller_kind="vgamepad", dry_run=False,
                 stop_after_matches=None, stop_after_seconds=None):
        super().__init__()
        self.profile = profile
        self.controller_kind = controller_kind
        self.dry_run = dry_run
        self.stop_after_matches = stop_after_matches
        self.stop_after_seconds = stop_after_seconds
        self._stop = threading.Event()

    def run(self):
        logger = get_logger()
        logger.buffer.callback = self.log_line.emit  # type: ignore[attr-defined]
        try:
            orch = build_orchestrator(
                self.profile, self.controller_kind, self.dry_run,
                on_update=self.status.emit,
                stop_after_matches=self.stop_after_matches,
                stop_after_seconds=self.stop_after_seconds,
            )
            orch.run(self._stop)
        finally:
            # Drop the callback so a stale bound signal can't fire after the
            # worker is gone (e.g. when the worker is recreated on restart).
            logger.buffer.callback = None  # type: ignore[attr-defined]
            self.stopped.emit()

    def stop(self):
        self._stop.set()
        if not self.wait(5000):
            get_logger().warning(
                "BotWorker did not stop within 5s; a Win32/input call may be "
                "blocking. Leaving it to finish in the background."
            )
