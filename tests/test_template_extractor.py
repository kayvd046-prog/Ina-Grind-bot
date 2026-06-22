import numpy as np
from ievr_bot.states import GameState
from ievr_bot.ocr import TextBox
from ievr_bot.recorder import RecordedFrame
from ievr_bot.template_extractor import extract_candidates, propose_crop


def _frame(tag):
    return np.full((100, 200, 3), tag, np.uint8)


def _rf(tag):
    return RecordedFrame(timestamp=float(tag), frame=_frame(tag))


class _Detector:
    """Maps frame tag (top-left pixel) to (state, score)."""
    def __init__(self, mapping):
        self.mapping = mapping

    def best_score(self, frame):
        return self.mapping[int(frame[0, 0, 0])]


class _Ocr:
    """Maps frame tag to a list of TextBoxes."""
    def __init__(self, mapping):
        self.mapping = mapping

    def read_boxes(self, frame):
        return self.mapping.get(int(frame[0, 0, 0]), [])


KEYWORDS = {GameState.GOAL: ["goal"], GameState.FULLTIME: ["full time"]}


# --- propose_crop -----------------------------------------------------------

def test_propose_crop_pads_and_clamps_matching_box():
    boxes = [TextBox("GOAL!", 0.9, (50, 40, 30, 10))]
    crop = propose_crop(boxes, ["goal"], (100, 200), pad=5)
    # padded by 5 on each side, clamped to frame (h=100, w=200)
    assert crop == (45, 35, 40, 20)


def test_propose_crop_unions_multiple_matching_boxes():
    boxes = [TextBox("GOAL", 0.9, (10, 10, 20, 10)),
             TextBox("goal!", 0.8, (60, 30, 10, 10))]
    crop = propose_crop(boxes, ["goal"], (100, 200), pad=0)
    # union: x 10..70, y 10..40 -> (10, 10, 60, 30)
    assert crop == (10, 10, 60, 30)


def test_propose_crop_clamps_to_frame_bounds():
    boxes = [TextBox("GOAL", 0.9, (0, 0, 30, 10))]
    crop = propose_crop(boxes, ["goal"], (100, 200), pad=20)
    # cannot go negative; left/top clamp to 0
    assert crop == (0, 0, 50, 30)


def test_propose_crop_no_match_returns_none():
    boxes = [TextBox("PRESS START", 0.9, (0, 0, 30, 10))]
    assert propose_crop(boxes, ["goal"], (100, 200), pad=5) is None


def test_propose_crop_uses_whole_word_match():
    boxes = [TextBox("goalkeeper", 0.9, (0, 0, 30, 10))]
    assert propose_crop(boxes, ["goal"], (100, 200), pad=5) is None


# --- extract_candidates -----------------------------------------------------

def test_groups_by_state_and_excludes_unknown():
    frames = [_rf(1), _rf(2), _rf(3)]
    det = _Detector({
        1: (GameState.GOAL, 0.9),
        2: (GameState.UNKNOWN, 0.0),
        3: (GameState.FULLTIME, 0.8),
    })
    ocr = _Ocr({})
    out = extract_candidates(frames, det, ocr, KEYWORDS, top_n=5)
    assert set(out) == {GameState.GOAL, GameState.FULLTIME}
    assert len(out[GameState.GOAL]) == 1


def test_keeps_top_n_by_score_descending():
    frames = [_rf(1), _rf(2), _rf(3), _rf(4)]
    det = _Detector({
        1: (GameState.GOAL, 0.7),
        2: (GameState.GOAL, 0.95),
        3: (GameState.GOAL, 0.6),
        4: (GameState.GOAL, 0.85),
    })
    out = extract_candidates(frames, det, _Ocr({}), KEYWORDS, top_n=2)
    scores = [c.score for c in out[GameState.GOAL]]
    assert scores == [0.95, 0.85]


def test_candidate_carries_proposed_crop():
    frames = [_rf(1)]
    det = _Detector({1: (GameState.GOAL, 0.9)})
    ocr = _Ocr({1: [TextBox("GOAL", 0.9, (50, 40, 30, 10))]})
    out = extract_candidates(frames, det, ocr, KEYWORDS, top_n=5)
    cand = out[GameState.GOAL][0]
    assert cand.crop == (42, 32, 46, 26)  # pad default 8, clamped
    assert int(cand.frame[0, 0, 0]) == 1


def test_candidate_crop_none_when_no_text_box_matches():
    frames = [_rf(1)]
    det = _Detector({1: (GameState.GOAL, 0.9)})
    ocr = _Ocr({1: [TextBox("nothing", 0.9, (0, 0, 10, 10))]})
    out = extract_candidates(frames, det, ocr, KEYWORDS, top_n=5)
    assert out[GameState.GOAL][0].crop is None
