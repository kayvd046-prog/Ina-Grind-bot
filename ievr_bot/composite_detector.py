"""Detector that tries OCR first and falls back to template matching."""
import numpy as np
from .states import GameState
from .vision import StateDetector


class CompositeDetector:
    def __init__(self, ocr_detector, template_detector) -> None:
        self.ocr = ocr_detector
        self.template = template_detector

    def best_score(self, frame: np.ndarray) -> tuple[GameState, float]:
        state, score = self.ocr.best_score(frame)
        if state != GameState.UNKNOWN:
            return (state, score)
        return self.template.best_score(frame)

    def detect(self, frame: np.ndarray) -> GameState:
        return self.best_score(frame)[0]


def build_detector(profile):
    """Select a detector from the profile's `detection` field.

    Falls back to template-only if OCR can't initialize (e.g. missing model)
    so the bot always runs.
    """
    from .logger import get_logger
    log = get_logger()
    template = StateDetector(profile.templates_dir, profile.match_threshold)
    n_templates = len(template.templates)

    if profile.detection == "template":
        if n_templates == 0:
            log.warning(
                "Template detection has no template images in %s — "
                "the bot will not recognize any screen. "
                "Capture templates in the GUI Templates tab.",
                profile.templates_dir,
            )
        else:
            log.info("Template detection active with %d template(s) loaded.", n_templates)
        return template

    from .ocr import make_ocr_engine
    from .ocr_detector import OcrStateDetector
    ocr_cfg = profile.ocr or {}
    try:
        engine = make_ocr_engine(ocr_cfg.get("lang", "en"))
    except Exception:
        log.exception(
            "OCR init failed — falling back to TEMPLATE-ONLY detection "
            "(%d template(s) loaded). Screens that OCR would read may go "
            "undetected.",
            n_templates,
        )
        return template
    ocr_det = OcrStateDetector(
        engine,
        ocr_cfg.get("keywords", {}),
        min_confidence=float(ocr_cfg.get("min_confidence", 0.5)),
        region=ocr_cfg.get("region"),
    )
    if profile.detection == "ocr":
        log.info("OCR detection active.")
        return ocr_det
    # composite (default)
    if n_templates == 0:
        log.info(
            "Composite detection active — OCR only, no template fallback "
            "(templates are optional; capture them in the Templates tab)."
        )
    else:
        log.info(
            "Composite detection active with %d fallback template(s).", n_templates
        )
    return CompositeDetector(ocr_det, template)
