import numpy as np
from ievr_bot.ocr import OcrEngine, make_ocr_engine


class _FakeEngine:
    def read(self, frame):
        return ["KICK OFF", "Commander"]


def test_fake_engine_satisfies_protocol():
    eng = _FakeEngine()
    assert isinstance(eng, OcrEngine)


def test_make_ocr_engine_returns_engine_with_read():
    eng = make_ocr_engine("en")
    assert hasattr(eng, "read")
