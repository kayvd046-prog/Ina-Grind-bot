import numpy as np
from ievr_bot.ocr_detector import OcrStateDetector
from ievr_bot.states import GameState

KEYWORDS = {
    "KICKOFF": ["kick off", "commander"],
    "FULLTIME": ["full time"],
    "GOAL": ["goal"],
}


class _Engine:
    def __init__(self, lines):
        self._lines = lines

    def read(self, frame):
        return self._lines


def _frame():
    return np.zeros((10, 10, 3), np.uint8)


def test_maps_text_to_state():
    det = OcrStateDetector(_Engine(["KICK OFF", "Press A"]), KEYWORDS)
    assert det.detect(_frame()) == GameState.KICKOFF


def test_more_keyword_hits_wins():
    # KICKOFF has two hits (kick off + commander), GOAL has one.
    det = OcrStateDetector(_Engine(["Kick Off", "COMMANDER", "goal"]), KEYWORDS)
    assert det.detect(_frame()) == GameState.KICKOFF


def test_below_confidence_is_unknown():
    det = OcrStateDetector(_Engine(["nothing relevant here"]), KEYWORDS,
                           min_confidence=0.5)
    state, score = det.best_score(_frame())
    assert state == GameState.UNKNOWN
    assert score == 0.0


def test_unknown_keyword_state_name_ignored():
    det = OcrStateDetector(_Engine(["full time"]),
                           {"NOT_A_STATE": ["x"], "FULLTIME": ["full time"]})
    assert det.detect(_frame()) == GameState.FULLTIME


def test_hits_below_confidence_is_unknown():
    # KICKOFF has 2 keywords; only one matches -> score 0.5, below 0.6 cutoff.
    det = OcrStateDetector(_Engine(["kick off"]), KEYWORDS, min_confidence=0.6)
    state, score = det.best_score(_frame())
    assert state == GameState.UNKNOWN
    assert score == 0.5


def test_word_boundary_avoids_substring_false_positive():
    # "goalkeeper" must NOT match the GOAL keyword "goal".
    det = OcrStateDetector(_Engine(["the goalkeeper saved it"]), KEYWORDS)
    assert det.detect(_frame()) == GameState.UNKNOWN


def test_higher_confidence_state_beats_partial_multi_keyword_match():
    # Real end-of-match screen: shows RESULTS + ITEMS + SPIRITS and a Rematch
    # button. "results" partially matches POST_MATCH (1 of 3 -> 0.33) but
    # "rematch" fully matches REMATCH (1 of 1 -> 1.0). The full match must win;
    # otherwise POST_MATCH wins the hit-count tie and its 0.33 score falls below
    # min_confidence, leaving the screen UNKNOWN (the rematch bug).
    kw = {
        "POST_MATCH": ["match result", "results", "next"],
        "REMATCH": ["rematch"],
    }
    eng = _Engine(["RESULTS", "ITEMS", "SPIRITS", "Rematch", "Return to Menu"])
    det = OcrStateDetector(eng, kw, min_confidence=0.5)
    state, score = det.best_score(_frame())
    assert state == GameState.REMATCH
    assert score == 1.0
