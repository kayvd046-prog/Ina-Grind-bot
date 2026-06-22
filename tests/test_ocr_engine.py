import numpy as np
from ievr_bot.ocr import OcrEngine, make_ocr_engine, TextBox, parse_rapidocr_result


class _FakeEngine:
    def read(self, frame):
        return ["KICK OFF", "Commander"]


def test_parse_rapidocr_result_empty_is_empty():
    assert parse_rapidocr_result(None) == []
    assert parse_rapidocr_result([]) == []


def test_parse_rapidocr_result_converts_polygon_to_bbox():
    # RapidOCR line: [box(4 points), text, score]
    result = [
        [[[10, 20], [110, 20], [110, 60], [10, 60]], "GOAL", 0.97],
    ]
    boxes = parse_rapidocr_result(result)
    assert boxes == [TextBox(text="GOAL", score=0.97, box=(10, 20, 100, 40))]


def test_parse_rapidocr_result_handles_skewed_polygon():
    # Non-rectangular polygon -> axis-aligned bounding box (min/max of points).
    result = [
        [[[5, 8], [50, 4], [52, 30], [3, 34]], "FULL TIME", 0.9],
    ]
    [tb] = parse_rapidocr_result(result)
    assert tb.box == (3, 4, 49, 30)
    assert tb.text == "FULL TIME"


def test_fake_engine_satisfies_protocol():
    eng = _FakeEngine()
    assert isinstance(eng, OcrEngine)


def test_make_ocr_engine_returns_engine_with_read():
    eng = make_ocr_engine("en")
    assert hasattr(eng, "read")
