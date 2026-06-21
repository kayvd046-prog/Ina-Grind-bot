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
