"""Session rewards overview: turn end-screen OCR text into item totals.

The end-of-match screens (REWARDS / POST_MATCH / REMATCH) list the items the
match paid out. Each time the bot *transitions onto* one of those screens the
orchestrator hands the frame to a RewardsTracker, which OCRs it and parses the
item lines. Screens within one match are merged taking the highest count per
item (the same list often appears on more than one screen), and the episode is
added to the session totals when the match is confirmed finished.

Parsing is heuristic by design: known UI words and numeric noise are dropped,
``<name> x<N>`` suffixes become counts, anything else counts as one item.
OCR misreads show up as separate rows; that is accepted for now.
"""
import re
from typing import Optional

from .states import GameState

REWARD_SCREENS = {GameState.REWARDS, GameState.POST_MATCH, GameState.REMATCH}

_QTY_RE = re.compile(r"^(.*?)\s*[x×]\s*(\d+)\s*$", re.IGNORECASE)
# Lines that are pure numbers / percentages / punctuation, e.g. "120", "+45%".
_NOISE_RE = re.compile(r"^[\d\s.,:;%+\-/*×x]*$", re.IGNORECASE)
_UI_WORDS = {
    "results", "next", "rematch", "return to menu", "items", "spirits",
    "rewards", "exp", "ok", "back", "menu", "total", "victory", "win",
    "lose", "draw", "ability learning report", "commander mode",
}


def parse_reward_lines(lines) -> dict[str, int]:
    """Extract ``{item name: count}`` from OCR text lines, taking the highest
    count when the same item appears more than once."""
    found: dict[str, int] = {}
    for raw in lines:
        line = raw.strip()
        if len(line) < 3 or _NOISE_RE.match(line):
            continue
        m = _QTY_RE.match(line)
        name, qty = (m.group(1).strip(), int(m.group(2))) if m else (line, 1)
        if not name or name.lower() in _UI_WORDS:
            continue
        found[name] = max(found.get(name, 0), qty)
    return found


class RewardsTracker:
    def __init__(self, ocr_engine=None) -> None:
        self.ocr_engine = ocr_engine
        self.totals: dict[str, int] = {}
        self.matches = 0
        self._episode: dict[str, int] = {}

    def observe_lines(self, lines) -> None:
        for name, qty in parse_reward_lines(lines).items():
            self._episode[name] = max(self._episode.get(name, 0), qty)

    def observe_frame(self, frame) -> None:
        if self.ocr_engine is None:
            return
        self.observe_lines([tb.text for tb in self.ocr_engine.read_boxes(frame)])

    def flush_match(self) -> None:
        for name, qty in self._episode.items():
            self.totals[name] = self.totals.get(name, 0) + qty
        self._episode = {}
        self.matches += 1
