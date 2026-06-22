"""Record one match by grabbing frames from a frame source.

Reuses the same frame sources as the bot (WindowCapture / ScreenCapture), so the
recording sees exactly what the bot will play against — and, with the window
backend, works without anything overlapping the game. Frames are kept in memory;
only the templates the user later picks are written to disk.
"""
import time
from dataclasses import dataclass
from typing import Callable, Optional
import numpy as np

from .logger import get_logger

# Safety cap: a 5-min match at ~2.5 fps is ~750 frames; 4000 is a generous
# ceiling that still bounds memory if the user forgets to stop.
DEFAULT_MAX_FRAMES = 4000


@dataclass
class RecordedFrame:
    timestamp: float
    frame: np.ndarray


class MatchRecorder:
    def __init__(self, source, interval: float = 0.4,
                 max_frames: int = DEFAULT_MAX_FRAMES,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.source = source
        self.interval = interval
        self.max_frames = max_frames
        self._sleep = sleep
        self.log = get_logger()

    def record(self, stop_event,
               on_frame: Optional[Callable[[np.ndarray], None]] = None
               ) -> list[RecordedFrame]:
        frames: list[RecordedFrame] = []
        while not stop_event.is_set() and len(frames) < self.max_frames:
            try:
                frame = self.source.grab()
            except Exception as exc:
                # A transient grab failure (window gone, black frame) must not
                # abort the recording; skip this frame and keep going.
                self.log.warning("Skipping frame, grab failed: %s", exc)
                self._sleep(self.interval)
                continue
            frames.append(RecordedFrame(timestamp=time.time(), frame=frame))
            if on_frame:
                on_frame(frame)
            self._sleep(self.interval)
        if len(frames) >= self.max_frames:
            self.log.info("Recording stopped: frame cap (%d) reached",
                          self.max_frames)
        return frames
