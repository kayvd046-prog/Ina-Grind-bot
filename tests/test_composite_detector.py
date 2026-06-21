import numpy as np
from ievr_bot.composite_detector import CompositeDetector
from ievr_bot.states import GameState


class _Det:
    def __init__(self, state, score):
        self._r = (state, score)

    def best_score(self, frame):
        return self._r

    def detect(self, frame):
        return self._r[0]


def _f():
    return np.zeros((4, 4, 3), np.uint8)


def test_ocr_wins_when_confident():
    comp = CompositeDetector(_Det(GameState.GOAL, 1.0),
                             _Det(GameState.MAIN_MENU, 0.9))
    assert comp.detect(_f()) == GameState.GOAL


def test_falls_back_to_template_when_ocr_unknown():
    comp = CompositeDetector(_Det(GameState.UNKNOWN, 0.0),
                             _Det(GameState.MAIN_MENU, 0.9))
    state, score = comp.best_score(_f())
    assert state == GameState.MAIN_MENU
    assert score == 0.9


def test_both_unknown_is_unknown():
    comp = CompositeDetector(_Det(GameState.UNKNOWN, 0.0),
                             _Det(GameState.UNKNOWN, 0.0))
    assert comp.detect(_f()) == GameState.UNKNOWN


def test_build_detector_falls_back_when_ocr_init_fails(tmp_path, monkeypatch):
    from ievr_bot import composite_detector as cd
    from ievr_bot.vision import StateDetector
    from ievr_bot.config import load_profile
    from pathlib import Path
    import ievr_bot.ocr as ocr_mod
    def _boom(lang="en"):
        raise RuntimeError("no model")
    monkeypatch.setattr(ocr_mod, "make_ocr_engine", _boom)
    PROFILES = Path(__file__).resolve().parents[1] / "profiles"
    profile = load_profile("pve", PROFILES)  # detection: composite
    det = cd.build_detector(profile)
    assert isinstance(det, StateDetector)
