import threading
from PySide6.QtCore import QThread, Signal
from ievr_bot.orchestrator import build_orchestrator
from ievr_bot.logger import get_logger


class BotWorker(QThread):
    status = Signal(object)
    log_line = Signal(str)
    stopped = Signal()

    def __init__(self, profile, controller_kind="vgamepad", dry_run=False):
        super().__init__()
        self.profile = profile
        self.controller_kind = controller_kind
        self.dry_run = dry_run
        self._stop = threading.Event()

    def run(self):
        logger = get_logger()
        logger.buffer.callback = self.log_line.emit  # type: ignore[attr-defined]
        orch = build_orchestrator(
            self.profile, self.controller_kind, self.dry_run,
            on_update=self.status.emit,
        )
        orch.run(self._stop)
        self.stopped.emit()

    def stop(self):
        self._stop.set()
        self.wait(5000)
