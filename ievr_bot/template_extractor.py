"""Turn recorded frames into per-state template candidates.

Runs the bot's own detector over the recording to label frames, then for each
state keeps the highest-confidence frames and proposes a crop region around the
text that identifies the state (so the saved template is a small, robust UI
element rather than a whole frame).
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import cv2
import numpy as np

from .states import GameState
from .ocr import TextBox

DEFAULT_PAD = 8


@dataclass
class Candidate:
    frame: np.ndarray
    score: float
    crop: Optional[tuple[int, int, int, int]]  # x, y, w, h


def _matches(text: str, keywords: list[str]) -> bool:
    low = text.lower()
    return any(re.search(r"\b" + re.escape(w.lower()) + r"\b", low)
               for w in keywords)


def propose_crop(text_boxes: list[TextBox], keywords: list[str],
                 frame_shape: tuple[int, int],
                 pad: int = DEFAULT_PAD
                 ) -> Optional[tuple[int, int, int, int]]:
    """Union of the boxes whose text matches a keyword (whole-word), padded and
    clamped to the frame. None if no box matches."""
    matched = [tb.box for tb in text_boxes if _matches(tb.text, keywords)]
    if not matched:
        return None
    x0 = min(b[0] for b in matched)
    y0 = min(b[1] for b in matched)
    x1 = max(b[0] + b[2] for b in matched)
    y1 = max(b[1] + b[3] for b in matched)
    h, w = frame_shape[0], frame_shape[1]
    x0 = max(0, x0 - pad)
    y0 = max(0, y0 - pad)
    x1 = min(w, x1 + pad)
    y1 = min(h, y1 + pad)
    return (x0, y0, x1 - x0, y1 - y0)


def extract_candidates(frames, detector, ocr_engine,
                       keywords: dict[GameState, list[str]],
                       top_n: int = 5,
                       pad: int = DEFAULT_PAD) -> dict[GameState, list[Candidate]]:
    grouped: dict[GameState, list[Candidate]] = {}
    for rf in frames:
        state, score = detector.best_score(rf.frame)
        if state == GameState.UNKNOWN:
            continue
        crop = propose_crop(ocr_engine.read_boxes(rf.frame),
                            keywords.get(state, []),
                            rf.frame.shape[:2], pad)
        grouped.setdefault(state, []).append(
            Candidate(frame=rf.frame, score=score, crop=crop))
    for state in grouped:
        grouped[state].sort(key=lambda c: c.score, reverse=True)
        grouped[state] = grouped[state][:top_n]
    return grouped


def save_template(frame: np.ndarray,
                  crop: Optional[tuple[int, int, int, int]],
                  dest: Path) -> None:
    """Write a template PNG: the cropped region (x, y, w, h) of the frame, or
    the whole frame when crop is None. Creates the parent directory."""
    if crop is not None:
        x, y, w, h = crop
        img = frame[y:y + h, x:x + w]
    else:
        img = frame
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dest), img)
