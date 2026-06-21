import numpy as np
from ievr_bot.ocr_detector import OcrStateDetector
from ievr_bot.composite_detector import CompositeDetector
from ievr_bot.vision import StateDetector
from ievr_bot.statemachine import StateMachine
from ievr_bot.watchdog import Watchdog
from ievr_bot.controller import NullController
from ievr_bot.orchestrator import Orchestrator
from ievr_bot.config import load_profile
from ievr_bot.capture import StaticFrameSource
from ievr_bot.states import GameState
from pathlib import Path

PROFILES = Path(__file__).resolve().parents[1] / "profiles"


class _Engine:
    def read(self, frame):
        return ["FULL TIME", "Match Result"]


def test_orchestrator_step_acts_on_ocr_state(tmp_path):
    profile = load_profile("pve", PROFILES)
    ocr = OcrStateDetector(_Engine(), profile.ocr["keywords"],
                           min_confidence=profile.ocr["min_confidence"])
    template = StateDetector(tmp_path, profile.match_threshold)  # empty -> UNKNOWN
    detector = CompositeDetector(ocr, template)
    controller = NullController()
    machine = StateMachine(profile, controller)
    source = StaticFrameSource(np.zeros((8, 8, 3), np.uint8))
    orch = Orchestrator(source, detector, machine, Watchdog(25), profile)

    upd = orch.step()

    assert upd.state == GameState.FULLTIME
    assert controller.presses == ["confirm"]  # terminal screen -> confirm
