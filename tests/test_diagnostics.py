import numpy as np
from ievr_bot.states import GameState
from ievr_bot.ocr import TextBox
from ievr_bot.diagnostics import diagnose_frame, format_report, save_frame, ScreenDiagnosis


class _Ocr:
    def __init__(self, boxes):
        self._b = boxes

    def read_boxes(self, frame):
        return self._b


class _Det:
    def __init__(self, res):
        self._r = res

    def best_score(self, frame):
        return self._r


def test_diagnose_frame_collects_ocr_and_state():
    frame = np.zeros((40, 80, 3), np.uint8)
    ocr = _Ocr([TextBox("Rematch", 0.95, (10, 10, 50, 12))])
    det = _Det((GameState.REMATCH, 0.99))
    d = diagnose_frame(frame, ocr, det)
    assert d.width == 80 and d.height == 40
    assert d.state == GameState.REMATCH and d.score == 0.99
    assert [t.text for t in d.ocr_lines] == ["Rematch"]


def test_format_report_lists_text_and_state():
    d = ScreenDiagnosis(80, 40, [TextBox("Rematch", 0.95, (1, 2, 3, 4))],
                        GameState.REMATCH, 0.99)
    s = format_report(d)
    assert "Rematch" in s          # the read text
    assert "REMATCH" in s          # the detected state


def test_format_report_flags_when_no_text():
    d = ScreenDiagnosis(80, 40, [], GameState.UNKNOWN, 0.0)
    s = format_report(d)
    assert "no text" in s.lower()


def test_save_frame_writes_png(tmp_path):
    p = save_frame(np.zeros((10, 10, 3), np.uint8), tmp_path)
    assert p.exists() and p.suffix == ".png"
    assert p.parent == tmp_path
