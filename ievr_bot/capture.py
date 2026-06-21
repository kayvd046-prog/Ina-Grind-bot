from typing import Protocol
import numpy as np


class FrameSource(Protocol):
    def grab(self) -> np.ndarray: ...


class StaticFrameSource:
    def __init__(self, frame: np.ndarray) -> None:
        self._frame = frame

    def grab(self) -> np.ndarray:
        return self._frame


class ScreenCapture:
    def __init__(self, region: dict | None = None) -> None:
        import mss
        self._sct = mss.mss()
        self.region = region or self._sct.monitors[1]

    def grab(self) -> np.ndarray:
        shot = self._sct.grab(self.region)
        arr = np.array(shot)  # BGRA
        return arr[:, :, :3]  # drop alpha -> BGR
