"""OCR engine wrapper.

A thin interface over an OCR backend so detectors depend on `read(frame) ->
list[str]` and tests can substitute a fake. The real backend is RapidOCR
(onnxruntime): pip-only, offline, no system install.
"""
from dataclasses import dataclass
from typing import Protocol, runtime_checkable
import numpy as np


@dataclass(frozen=True)
class TextBox:
    """One recognized text line and its axis-aligned bounding box.

    box is (x, y, w, h) in frame pixels. Used to propose a crop region around
    the text that identifies a state.
    """
    text: str
    score: float
    box: tuple[int, int, int, int]


def parse_rapidocr_result(result) -> list[TextBox]:
    """Convert RapidOCR's raw result (list of [polygon, text, score], or None)
    into TextBoxes with axis-aligned bounding boxes."""
    if not result:
        return []
    boxes: list[TextBox] = []
    for line in result:
        poly, text, score = line[0], line[1], line[2]
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        x, y = int(min(xs)), int(min(ys))
        w, h = int(max(xs)) - x, int(max(ys)) - y
        boxes.append(TextBox(text=str(text), score=float(score), box=(x, y, w, h)))
    return boxes


@runtime_checkable
class OcrEngine(Protocol):
    def read(self, frame: np.ndarray) -> list[str]: ...


class RapidOcrEngine:
    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR
        self._ocr = RapidOCR()

    def read_boxes(self, frame: np.ndarray) -> list[TextBox]:
        # RapidOCR returns (result, elapse); result is a list of
        # [box, text, score] or None when nothing is found.
        result, _ = self._ocr(frame)
        return parse_rapidocr_result(result)

    def read(self, frame: np.ndarray) -> list[str]:
        return [tb.text for tb in self.read_boxes(frame)]


def make_ocr_engine(lang: str = "en") -> OcrEngine:
    # lang is accepted for forward-compatibility; RapidOCR's default models
    # cover English. Kept in the signature so callers/config stay stable.
    return RapidOcrEngine()
