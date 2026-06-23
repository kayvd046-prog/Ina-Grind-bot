"""Inspect what the bot sees on a single frame.

Shared by the CLI tool and the GUI "Diagnose current screen" button: given a
frame plus an OCR engine and the detector, report every text line OCR reads and
which GameState the detector picks. This is how you tell whether a screen is
detectable by OCR (and with which keyword) or needs a template.
"""
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np

from .states import GameState
from .ocr import TextBox


@dataclass
class ScreenDiagnosis:
    width: int
    height: int
    ocr_lines: list[TextBox]
    state: GameState
    score: float


def diagnose_frame(frame: np.ndarray, ocr_engine, detector) -> ScreenDiagnosis:
    boxes = ocr_engine.read_boxes(frame)
    state, score = detector.best_score(frame)
    h, w = frame.shape[:2]
    return ScreenDiagnosis(width=w, height=h, ocr_lines=list(boxes),
                           state=state, score=score)


def format_report(d: ScreenDiagnosis) -> str:
    lines = [f"Frame {d.width}x{d.height}",
             f"Detected state: {d.state.name}  (score {d.score:.2f})",
             "OCR text lines:"]
    if not d.ocr_lines:
        lines.append("  (OCR read no text on this screen — "
                     "this screen likely needs a template, not a keyword)")
    else:
        for tb in d.ocr_lines:
            lines.append(f"  {tb.text!r}  score={tb.score:.2f}  box={tb.box}")
    return "\n".join(lines)


def save_frame(frame: np.ndarray, out_dir) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"screen-{stamp}.png"
    cv2.imwrite(str(path), frame)
    return path
