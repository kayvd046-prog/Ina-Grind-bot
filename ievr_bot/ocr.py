"""OCR engine wrapper.

A thin interface over an OCR backend so detectors depend on `read(frame) ->
list[str]` and tests can substitute a fake. The real backend is RapidOCR
(onnxruntime): pip-only, offline, no system install.
"""
from typing import Protocol, runtime_checkable
import numpy as np


@runtime_checkable
class OcrEngine(Protocol):
    def read(self, frame: np.ndarray) -> list[str]: ...


class RapidOcrEngine:
    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR
        self._ocr = RapidOCR()

    def read(self, frame: np.ndarray) -> list[str]:
        # RapidOCR returns (result, elapse); result is a list of
        # [box, text, score] or None when nothing is found.
        result, _ = self._ocr(frame)
        if not result:
            return []
        return [str(line[1]) for line in result]


def make_ocr_engine(lang: str = "en") -> OcrEngine:
    # lang is accepted for forward-compatibility; RapidOCR's default models
    # cover English. Kept in the signature so callers/config stay stable.
    return RapidOcrEngine()
