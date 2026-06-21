import numpy as np
import cv2
from ievr_bot.vision import StateDetector
from ievr_bot.states import GameState


def _make_templates(tmp_path):
    # Two visually distinct templates (deterministic random patterns) so the
    # detector has to tell them apart, like real UI screenshots.
    rng = np.random.default_rng(0)
    menu = rng.integers(0, 256, (30, 30, 3), dtype=np.uint8)
    kick = rng.integers(0, 256, (30, 30, 3), dtype=np.uint8)
    cv2.imwrite(str(tmp_path / "main_menu.png"), menu)
    cv2.imwrite(str(tmp_path / "kickoff.png"), kick)
    return menu, kick


def test_detect_matches_correct_state(tmp_path):
    _menu, kick = _make_templates(tmp_path)
    det = StateDetector(tmp_path, threshold=0.8)
    # Frame embeds the exact kickoff template inside a larger image
    frame = np.full((100, 100, 3), 50, np.uint8)
    frame[60:90, 60:90] = kick
    assert det.detect(frame) == GameState.KICKOFF


def test_detect_returns_unknown_when_no_match(tmp_path):
    _make_templates(tmp_path)
    det = StateDetector(tmp_path, threshold=0.95)
    frame = np.full((100, 100, 3), 128, np.uint8)  # flat gray, no pattern
    assert det.detect(frame) == GameState.UNKNOWN
