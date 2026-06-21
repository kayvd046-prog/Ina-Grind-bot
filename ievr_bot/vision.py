from pathlib import Path
import cv2
import numpy as np
from .states import GameState


class StateDetector:
    def __init__(self, templates_dir: Path, threshold: float = 0.85) -> None:
        self.threshold = threshold
        self.templates: dict[GameState, np.ndarray] = {}
        for state in GameState:
            path = Path(templates_dir) / f"{state.name.lower()}.png"
            if path.exists():
                img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    self.templates[state] = img

    def best_score(self, frame: np.ndarray) -> tuple[GameState, float]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        best_state = GameState.UNKNOWN
        best = 0.0
        for state, tmpl in self.templates.items():
            if tmpl.shape[0] > gray.shape[0] or tmpl.shape[1] > gray.shape[1]:
                continue
            res = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
            _, score, _, _ = cv2.minMaxLoc(res)
            if score > best:
                best, best_state = score, state
        return (best_state if best >= self.threshold else GameState.UNKNOWN, best)

    def detect(self, frame: np.ndarray) -> GameState:
        return self.best_score(frame)[0]
