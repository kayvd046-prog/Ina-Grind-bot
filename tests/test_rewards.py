"""Session rewards overview: parse item lines from end-screen OCR text."""
from ievr_bot.rewards import parse_reward_lines, RewardsTracker, REWARD_SCREENS
from ievr_bot.states import GameState


# --- parsing ---------------------------------------------------------------

def test_parses_item_with_quantity_suffix():
    assert parse_reward_lines(["Fire Pinwheel x2"]) == {"Fire Pinwheel": 2}
    assert parse_reward_lines(["Aura Ball ×3"]) == {"Aura Ball": 3}
    assert parse_reward_lines(["Sharp Cleats X 4"]) == {"Sharp Cleats": 4}


def test_item_without_quantity_counts_as_one():
    assert parse_reward_lines(["Training Bib"]) == {"Training Bib": 1}


def test_ui_words_and_noise_are_filtered():
    lines = ["RESULTS", "Next", "Rematch", "Return to Menu", "Items",
             "Spirits", "Rewards", "EXP", "120", "+45%", "", "  ", "OK",
             "Fire Pinwheel x2"]
    assert parse_reward_lines(lines) == {"Fire Pinwheel": 2}


def test_duplicate_lines_take_the_highest_count():
    # The same screen can be OCR'd more than once during one match.
    lines = ["Fire Pinwheel x2", "Fire Pinwheel x2"]
    assert parse_reward_lines(lines) == {"Fire Pinwheel": 2}


# --- tracker ---------------------------------------------------------------

class FakeBox:
    def __init__(self, text):
        self.text = text
        self.score = 0.9
        self.box = (0, 0, 10, 10)


class FakeEngine:
    def __init__(self, lines):
        self.lines = lines
        self.calls = 0

    def read_boxes(self, frame):
        self.calls += 1
        return [FakeBox(t) for t in self.lines]


def test_tracker_accumulates_over_matches():
    t = RewardsTracker()
    t.observe_lines(["Fire Pinwheel x2", "Training Bib"])
    t.flush_match()
    t.observe_lines(["Fire Pinwheel x1"])
    t.flush_match()
    assert t.matches == 2
    assert t.totals == {"Fire Pinwheel": 3, "Training Bib": 1}


def test_episode_merges_screens_without_double_counting():
    t = RewardsTracker()
    # REWARDS screen and POST_MATCH screen both list the same item once.
    t.observe_lines(["Fire Pinwheel x2"])
    t.observe_lines(["Fire Pinwheel x2", "Aura Ball"])
    t.flush_match()
    assert t.totals == {"Fire Pinwheel": 2, "Aura Ball": 1}


def test_flush_without_observations_still_counts_the_match():
    t = RewardsTracker()
    t.flush_match()
    assert t.matches == 1
    assert t.totals == {}


def test_observe_frame_uses_engine_and_tolerates_missing_engine():
    eng = FakeEngine(["Training Bib"])
    t = RewardsTracker(ocr_engine=eng)
    t.observe_frame(object())
    t.flush_match()
    assert eng.calls == 1
    assert t.totals == {"Training Bib": 1}
    # No engine -> silently a no-op, never raises.
    t2 = RewardsTracker(ocr_engine=None)
    t2.observe_frame(object())
    t2.flush_match()
    assert t2.totals == {}


def test_reward_screens_are_the_end_of_match_screens():
    assert REWARD_SCREENS == {GameState.REWARDS, GameState.POST_MATCH,
                              GameState.REMATCH}
