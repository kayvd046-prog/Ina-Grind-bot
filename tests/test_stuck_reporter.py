"""Auto-diagnose on watchdog recovery: save frame + report to the diag dir."""
import numpy as np
from ievr_bot.states import GameState
from ievr_bot.stuck_reporter import StuckReporter, find_ocr_engine


def _frame():
    return np.zeros((20, 30, 3), np.uint8)


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class FakeOcrEngine:
    def read_boxes(self, frame):
        from ievr_bot.ocr import TextBox
        return [TextBox(text="Rematch", score=0.9, box=(0, 0, 10, 10))]


def test_report_saves_png_and_txt_with_state(tmp_path):
    rep = StuckReporter(tmp_path / "diag", now=FakeClock())
    path = rep.report(_frame(), GameState.UNKNOWN, 0.12)
    assert path is not None and path.exists() and path.suffix == ".png"
    txt = path.with_suffix(".txt")
    assert txt.exists()
    body = txt.read_text(encoding="utf-8")
    assert "UNKNOWN" in body and "0.12" in body


def test_report_includes_ocr_lines_when_engine_available(tmp_path):
    rep = StuckReporter(tmp_path, ocr_engine=FakeOcrEngine(), now=FakeClock())
    path = rep.report(_frame(), GameState.UNKNOWN, 0.0)
    body = path.with_suffix(".txt").read_text(encoding="utf-8")
    assert "Rematch" in body


def test_report_is_rate_limited(tmp_path):
    clock = FakeClock()
    rep = StuckReporter(tmp_path, min_interval=60.0, now=clock)
    assert rep.report(_frame(), GameState.UNKNOWN, 0.0) is not None
    clock.t = 30.0
    assert rep.report(_frame(), GameState.UNKNOWN, 0.0) is None
    clock.t = 61.0
    assert rep.report(_frame(), GameState.UNKNOWN, 0.0) is not None
    assert len(list(tmp_path.glob("stuck-*.png"))) == 2


def test_old_reports_are_pruned(tmp_path):
    clock = FakeClock()
    rep = StuckReporter(tmp_path, min_interval=0.0, max_files=2, now=clock)
    for i in range(4):
        clock.t = float(i * 100)
        assert rep.report(_frame(), GameState.UNKNOWN, 0.0) is not None
    assert len(list(tmp_path.glob("stuck-*.png"))) == 2
    # Every remaining png still has its companion report.
    for png in tmp_path.glob("stuck-*.png"):
        assert png.with_suffix(".txt").exists()


def test_find_ocr_engine_on_ocr_and_composite_detectors():
    class Engine:
        pass

    class OcrDet:
        def __init__(self):
            self.engine = Engine()

    class Composite:
        def __init__(self):
            self.ocr = OcrDet()

    class TemplateOnly:
        pass

    assert isinstance(find_ocr_engine(OcrDet()), Engine)
    assert isinstance(find_ocr_engine(Composite()), Engine)
    assert find_ocr_engine(TemplateOnly()) is None
