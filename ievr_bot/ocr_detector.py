"""Detect game state from on-screen text via OCR keyword matching."""
import re
import numpy as np
from .states import GameState
from .ocr import OcrEngine


class OcrStateDetector:
    def __init__(self, engine: OcrEngine, keywords: dict[str, list[str]],
                 min_confidence: float = 0.5, region: dict | None = None) -> None:
        self.engine = engine
        self.min_confidence = min_confidence
        self.region = region
        # Resolve state names to GameState once; skip names that aren't states.
        self.keywords: dict[GameState, list[str]] = {}
        for name, words in keywords.items():
            try:
                state = GameState[name]
            except KeyError:
                continue
            self.keywords[state] = [w.lower() for w in words]

    def _crop(self, frame: np.ndarray) -> np.ndarray:
        if self.region is None:
            return frame
        r = self.region
        return frame[r["top"]:r["top"] + r["height"],
                     r["left"]:r["left"] + r["width"]]

    def best_score(self, frame: np.ndarray) -> tuple[GameState, float]:
        text = " ".join(self.engine.read(self._crop(frame))).lower()
        # Rank by normalized confidence (matched keywords / total keywords), NOT
        # by raw hit count: a state that matches all of its keywords (e.g.
        # REMATCH 1/1 = 1.0) must beat one that matches only some of more
        # keywords (e.g. POST_MATCH 1/3 = 0.33) on a screen where both appear.
        # On a tie in score, the first state in keyword insertion order wins.
        best_state, best_score = GameState.UNKNOWN, 0.0
        for state, words in self.keywords.items():
            if not words:
                continue
            hits = sum(1 for w in words if re.search(r"\b" + re.escape(w) + r"\b", text))
            score = hits / len(words)
            if score > best_score:
                best_state, best_score = state, score
        if best_score == 0.0:
            return (GameState.UNKNOWN, 0.0)
        if best_score < self.min_confidence:
            return (GameState.UNKNOWN, best_score)
        return (best_state, best_score)

    def detect(self, frame: np.ndarray) -> GameState:
        return self.best_score(frame)[0]
