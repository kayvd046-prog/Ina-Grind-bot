"""Detect game state from on-screen text via OCR keyword matching."""
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
        best_state, best_hits, best_total = GameState.UNKNOWN, 0, 1
        # On a tie in hit count, the first state in keyword insertion order wins (strict >).
        for state, words in self.keywords.items():
            hits = sum(1 for w in words if w in text)
            if hits > best_hits:
                best_state, best_hits, best_total = state, hits, len(words)
        if best_hits == 0:
            return (GameState.UNKNOWN, 0.0)
        score = best_hits / best_total
        if score < self.min_confidence:
            return (GameState.UNKNOWN, score)
        return (best_state, score)

    def detect(self, frame: np.ndarray) -> GameState:
        return self.best_score(frame)[0]
