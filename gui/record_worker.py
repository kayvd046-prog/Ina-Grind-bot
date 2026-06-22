import threading
from PySide6.QtCore import QThread, Signal
from ievr_bot.capture import build_frame_source
from ievr_bot.recorder import MatchRecorder
from ievr_bot.logger import get_logger


class RecordWorker(QThread):
    """Records one match on a background thread, emitting a live preview and a
    running frame count, then the full list of RecordedFrames when stopped."""
    preview = Signal(object)   # np.ndarray frame
    count = Signal(int)        # frames captured so far
    done = Signal(object)      # list[RecordedFrame]
    error = Signal(str)

    def __init__(self, profile):
        super().__init__()
        self.profile = profile
        self._stop = threading.Event()
        self._n = 0

    def run(self):
        try:
            source = build_frame_source(self.profile)
            interval = float(self.profile.timings.get("poll_interval", 0.4))
            recorder = MatchRecorder(source, interval=interval)
            self._n = 0

            def on_frame(frame):
                self._n += 1
                self.preview.emit(frame)
                self.count.emit(self._n)

            frames = recorder.record(self._stop, on_frame=on_frame)
            self.done.emit(frames)
        except Exception as exc:  # building the source / unexpected failure
            get_logger().exception("Recording failed")
            self.error.emit(str(exc))
            self.done.emit([])

    def stop(self):
        self._stop.set()
        if not self.wait(5000):
            get_logger().warning("RecordWorker did not stop within 5s")
