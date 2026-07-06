"""Save what the bot saw whenever the watchdog has to recover.

When a run gets stuck on an unrecognized screen the user is usually not
watching. This writes the offending frame plus a small text report (detected
state, score, and every OCR line) to the diag directory, rate-limited and
pruned, so the stall can be diagnosed afterwards — same idea as the GUI's
"Diagnose current screen" button, but automatic.
"""
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import cv2
import numpy as np

from .states import GameState


def find_ocr_engine(detector):
    """Best-effort extraction of the OCR engine from any detector flavour
    (OcrStateDetector has .engine, CompositeDetector nests it under .ocr,
    template-only detectors have neither)."""
    engine = getattr(detector, "engine", None)
    if engine is not None:
        return engine
    return getattr(getattr(detector, "ocr", None), "engine", None)


class StuckReporter:
    def __init__(self, out_dir, ocr_engine=None, min_interval: float = 120.0,
                 max_files: int = 30,
                 now: Callable[[], float] = time.monotonic) -> None:
        self.out_dir = Path(out_dir)
        self.ocr_engine = ocr_engine
        self.min_interval = float(min_interval)
        self.max_files = int(max_files)
        self._now = now
        self._last: Optional[float] = None
        self._seq = 0

    def report(self, frame: np.ndarray, state: GameState,
               score: float) -> Optional[Path]:
        t = self._now()
        if self._last is not None and (t - self._last) < self.min_interval:
            return None
        self._last = t
        self._seq += 1
        self.out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.out_dir / f"stuck-{stamp}-{self._seq:03d}.png"
        cv2.imwrite(str(path), frame)
        path.with_suffix(".txt").write_text(
            self._describe(frame, state, score), encoding="utf-8")
        self._prune()
        return path

    def _describe(self, frame: np.ndarray, state: GameState,
                  score: float) -> str:
        h, w = frame.shape[:2]
        lines = [f"Watchdog recovery on {w}x{h} frame",
                 f"Detected state: {state.name}  (score {score:.2f})",
                 "OCR text lines:"]
        if self.ocr_engine is None:
            lines.append("  (no OCR engine available)")
        else:
            try:
                boxes = list(self.ocr_engine.read_boxes(frame))
            except Exception as exc:
                lines.append(f"  (OCR failed: {exc})")
                return "\n".join(lines)
            for tb in boxes:
                lines.append(f"  {tb.text!r}  score={tb.score:.2f}  box={tb.box}")
            if not boxes:
                lines.append("  (OCR read no text on this screen)")
        return "\n".join(lines)

    def _prune(self) -> None:
        if self.max_files <= 0:
            return
        pngs = sorted(self.out_dir.glob("stuck-*.png"))
        for old in pngs[:-self.max_files]:
            old.unlink(missing_ok=True)
            old.with_suffix(".txt").unlink(missing_ok=True)
