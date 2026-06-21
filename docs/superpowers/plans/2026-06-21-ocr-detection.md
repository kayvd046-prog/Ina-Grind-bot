# OCR-Primary State Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the bot detect game screens by reading on-screen text (OCR), falling back to template matching, so it works without any manually captured reference screenshots.

**Architecture:** Add an `OcrStateDetector` (OCR engine + per-state keyword map) and a `CompositeDetector` that tries OCR first and falls back to the existing template `StateDetector`. Profile gains `detection` and `ocr` config. Capture and input are unchanged (EAC-safe).

**Tech Stack:** Python 3.14, OpenCV, NumPy, RapidOCR (`rapidocr-onnxruntime`), PyYAML, PySide6, pytest.

## Global Constraints

- UI language is **English**; keyword lists are lowercase English substrings.
- Do **not** touch `capture.py` or `controller.py` (no memory reading, no input changes).
- OCR engine is wrapped behind a thin interface so tests use a fake — **never** call real RapidOCR in unit tests.
- All detectors expose the same interface: `best_score(frame) -> tuple[GameState, float]` and `detect(frame) -> GameState`.
- New profile fields must have defaults so existing profiles without them still load.
- Run tests with `.venv\Scripts\python -m pytest`. Existing 25 tests must stay green.

---

### Task 1: Profile gains `detection` and `ocr` fields

**Files:**
- Modify: `ievr_bot/config.py:10-44`
- Modify: `tests/test_config.py`
- Modify: `profiles/pve.yaml`, `profiles/ranked.yaml`

**Interfaces:**
- Consumes: existing `load_profile(name, profiles_dir) -> Profile`.
- Produces: `Profile` with new fields `detection: str = "composite"` and `ocr: dict` (default `{}`). Used by Task 4 (`CompositeDetector` wiring) and Task 2/3.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_config.py`:

```python
def test_profile_has_detection_and_ocr_defaults(tmp_path):
    (tmp_path / "min.yaml").write_text(
        "name: min\nmode: pve\ntemplates_subdir: pve\n"
        "button_map: {confirm: A, cancel: B, commander_toggle: Y, menu: START}\n"
        "timings: {}\n"
    )
    p = load_profile("min", tmp_path)
    assert p.detection == "composite"   # default when absent
    assert p.ocr == {}                  # default when absent


def test_profile_reads_detection_and_ocr(tmp_path):
    (tmp_path / "ocr.yaml").write_text(
        "name: ocr\nmode: pve\ntemplates_subdir: pve\n"
        "detection: ocr\n"
        "ocr: {lang: en, min_confidence: 0.5, keywords: {GOAL: ['goal']}}\n"
        "button_map: {confirm: A, cancel: B, commander_toggle: Y, menu: START}\n"
        "timings: {}\n"
    )
    p = load_profile("ocr", tmp_path)
    assert p.detection == "ocr"
    assert p.ocr["min_confidence"] == 0.5
    assert p.ocr["keywords"]["GOAL"] == ["goal"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_config.py::test_profile_has_detection_and_ocr_defaults -v`
Expected: FAIL with `AttributeError: 'Profile' object has no attribute 'detection'`

- [ ] **Step 3: Add the fields**

In `ievr_bot/config.py`, add to the `Profile` dataclass (after `window_title`):

```python
    detection: str = "composite"  # "ocr" | "template" | "composite"
    ocr: dict = field(default_factory=dict)
```

Add `field` to the dataclasses import at the top:

```python
from dataclasses import dataclass, field
```

In `load_profile`, add to the `Profile(...)` constructor call (after `window_title=...`):

```python
        detection=str(data.get("detection", "composite")),
        ocr=data.get("ocr", {}) or {},
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_config.py -v`
Expected: PASS (all config tests, old and new)

- [ ] **Step 5: Add config blocks to the shipped profiles**

Append to `profiles/pve.yaml`:

```yaml
detection: composite        # ocr | template | composite
ocr:
  lang: en
  min_confidence: 0.5
  region: null              # null = whole frame
  keywords:
    MAIN_MENU:   ["press start", "continue", "play"]
    KICKOFF:     ["kick off", "commander"]
    HALFTIME:    ["half time"]
    GOAL:        ["goal"]
    FULLTIME:    ["full time"]
    REWARDS:     ["reward", "rewards"]
    POST_MATCH:  ["match result", "results", "next"]
    LOADING:     ["loading", "now loading"]
    ERROR_DIALOG: ["error", "disconnected", "communication"]
```

Append the same block to `profiles/ranked.yaml` (adjust later if ranked screens differ).

- [ ] **Step 6: Run the full suite, then commit**

Run: `.venv\Scripts\python -m pytest`
Expected: PASS (all tests)

```bash
git add ievr_bot/config.py tests/test_config.py profiles/pve.yaml profiles/ranked.yaml
git commit -m "feat: add detection/ocr fields to Profile"
```

---

### Task 2: OCR engine wrapper

**Files:**
- Create: `ievr_bot/ocr.py`
- Test: `tests/test_ocr_engine.py`

**Interfaces:**
- Produces:
  - Protocol `OcrEngine` with `read(frame: np.ndarray) -> list[str]` (returns recognized text lines).
  - `RapidOcrEngine` implementing it (lazy-imports `rapidocr_onnxruntime`).
  - `make_ocr_engine(lang: str = "en") -> OcrEngine`.
- Consumed by Task 3 (`OcrStateDetector`) and Task 4 (wiring).

- [ ] **Step 1: Write the failing test**

Create `tests/test_ocr_engine.py`:

```python
import numpy as np
from ievr_bot.ocr import OcrEngine, make_ocr_engine


class _FakeEngine:
    def read(self, frame):
        return ["KICK OFF", "Commander"]


def test_fake_engine_satisfies_protocol():
    eng = _FakeEngine()
    assert isinstance(eng, OcrEngine)


def test_make_ocr_engine_returns_engine_with_read():
    eng = make_ocr_engine("en")
    assert hasattr(eng, "read")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_ocr_engine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ievr_bot.ocr'`

- [ ] **Step 3: Implement the wrapper**

Create `ievr_bot/ocr.py`:

```python
"""OCR engine wrapper.

A thin interface over an OCR backend so detectors depend on `read(frame) ->
list[str]` and tests can substitute a fake. The real backend is RapidOCR
(onnxruntime): pip-only, offline, no system install.
"""
from typing import Protocol, runtime_checkable
import numpy as np


@runtime_checkable
class OcrEngine(Protocol):
    def read(self, frame: np.ndarray) -> list[str]: ...


class RapidOcrEngine:
    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR
        self._ocr = RapidOCR()

    def read(self, frame: np.ndarray) -> list[str]:
        # RapidOCR returns (result, elapse); result is a list of
        # [box, text, score] or None when nothing is found.
        result, _ = self._ocr(frame)
        if not result:
            return []
        return [str(line[1]) for line in result]


def make_ocr_engine(lang: str = "en") -> OcrEngine:
    # lang is accepted for forward-compatibility; RapidOCR's default models
    # cover English. Kept in the signature so callers/config stay stable.
    return RapidOcrEngine()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests/test_ocr_engine.py::test_fake_engine_satisfies_protocol -v`
Expected: PASS

Note: `test_make_ocr_engine_returns_engine_with_read` constructs the real engine and requires `rapidocr-onnxruntime` installed (Task 6 adds it to requirements). If it is not yet installed, run only the protocol test for now; the full file passes after Task 6.

- [ ] **Step 5: Commit**

```bash
git add ievr_bot/ocr.py tests/test_ocr_engine.py
git commit -m "feat: add OCR engine wrapper (RapidOCR)"
```

---

### Task 3: OcrStateDetector (keyword → state)

**Files:**
- Create: `ievr_bot/ocr_detector.py`
- Test: `tests/test_ocr_detector.py`

**Interfaces:**
- Consumes: `OcrEngine` (from `ievr_bot.ocr`), `GameState` (from `ievr_bot.states`).
- Produces:
  - `OcrStateDetector(engine: OcrEngine, keywords: dict[str, list[str]], min_confidence: float = 0.5, region: dict | None = None)`.
  - Methods `best_score(frame) -> tuple[GameState, float]` and `detect(frame) -> GameState`.
- Consumed by Task 4 (`CompositeDetector`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_ocr_detector.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_ocr_detector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ievr_bot.ocr_detector'`

- [ ] **Step 3: Implement the detector**

Create `ievr_bot/ocr_detector.py`:

```python
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
        if not self.region:
            return frame
        r = self.region
        return frame[r["top"]:r["top"] + r["height"],
                     r["left"]:r["left"] + r["width"]]

    def best_score(self, frame: np.ndarray) -> tuple[GameState, float]:
        text = " ".join(self.engine.read(self._crop(frame))).lower()
        best_state, best_hits, best_total = GameState.UNKNOWN, 0, 1
        for state, words in self.keywords.items():
            hits = sum(1 for w in words if w in text)
            if hits > best_hits:
                best_state, best_hits, best_total = state, hits, len(words)
        if best_hits == 0:
            return (GameState.UNKNOWN, 0.0)
        score = best_hits / max(best_total, 1)
        if score < self.min_confidence:
            return (GameState.UNKNOWN, score)
        return (best_state, score)

    def detect(self, frame: np.ndarray) -> GameState:
        return self.best_score(frame)[0]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_ocr_detector.py -v`
Expected: PASS (all four tests)

- [ ] **Step 5: Commit**

```bash
git add ievr_bot/ocr_detector.py tests/test_ocr_detector.py
git commit -m "feat: add OcrStateDetector keyword mapping"
```

---

### Task 4: CompositeDetector + orchestrator wiring

**Files:**
- Create: `ievr_bot/composite_detector.py`
- Test: `tests/test_composite_detector.py`
- Modify: `ievr_bot/orchestrator.py:80-101`

**Interfaces:**
- Consumes: `OcrStateDetector` (Task 3), `StateDetector` (`ievr_bot.vision`), `make_ocr_engine` (Task 2), `Profile` (Task 1).
- Produces:
  - `CompositeDetector(ocr_detector, template_detector)` with `best_score(frame)` / `detect(frame)`.
  - `build_detector(profile) -> detector` helper used by `build_orchestrator`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_composite_detector.py`:

```python
import numpy as np
from ievr_bot.composite_detector import CompositeDetector
from ievr_bot.states import GameState


class _Det:
    def __init__(self, state, score):
        self._r = (state, score)

    def best_score(self, frame):
        return self._r

    def detect(self, frame):
        return self._r[0]


def _f():
    return np.zeros((4, 4, 3), np.uint8)


def test_ocr_wins_when_confident():
    comp = CompositeDetector(_Det(GameState.GOAL, 1.0),
                             _Det(GameState.MAIN_MENU, 0.9))
    assert comp.detect(_f()) == GameState.GOAL


def test_falls_back_to_template_when_ocr_unknown():
    comp = CompositeDetector(_Det(GameState.UNKNOWN, 0.0),
                             _Det(GameState.MAIN_MENU, 0.9))
    state, score = comp.best_score(_f())
    assert state == GameState.MAIN_MENU
    assert score == 0.9


def test_both_unknown_is_unknown():
    comp = CompositeDetector(_Det(GameState.UNKNOWN, 0.0),
                             _Det(GameState.UNKNOWN, 0.0))
    assert comp.detect(_f()) == GameState.UNKNOWN
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_composite_detector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ievr_bot.composite_detector'`

- [ ] **Step 3: Implement CompositeDetector + build_detector**

Create `ievr_bot/composite_detector.py`:

```python
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
    template = StateDetector(profile.templates_dir, profile.match_threshold)
    if profile.detection == "template":
        return template

    from .ocr import make_ocr_engine
    from .ocr_detector import OcrStateDetector
    ocr_cfg = profile.ocr or {}
    try:
        engine = make_ocr_engine(ocr_cfg.get("lang", "en"))
    except Exception:
        get_logger().exception("OCR init failed; using template detection only")
        return template
    ocr_det = OcrStateDetector(
        engine,
        ocr_cfg.get("keywords", {}),
        min_confidence=float(ocr_cfg.get("min_confidence", 0.5)),
        region=ocr_cfg.get("region"),
    )
    if profile.detection == "ocr":
        return ocr_det
    return CompositeDetector(ocr_det, template)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_composite_detector.py -v`
Expected: PASS (all three tests)

- [ ] **Step 5: Wire build_detector into the orchestrator**

In `ievr_bot/orchestrator.py`, inside `build_orchestrator`, replace this line:

```python
    detector = StateDetector(profile.templates_dir, profile.match_threshold)
```

with:

```python
    from .composite_detector import build_detector
    detector = build_detector(profile)
```

Remove the now-unused `from .vision import StateDetector` line in
`build_orchestrator` (it's imported inside `build_detector`). Leave the other
local imports (`ScreenCapture`, `WindowCapture`, `make_controller`,
`StateMachine`, `Watchdog`) untouched.

- [ ] **Step 6: Run the full suite**

Run: `.venv\Scripts\python -m pytest`
Expected: PASS. The existing `test_orchestrator.py` builds via injected
sources/detectors, so wiring stays green.

- [ ] **Step 7: Commit**

```bash
git add ievr_bot/composite_detector.py tests/test_composite_detector.py ievr_bot/orchestrator.py
git commit -m "feat: composite OCR+template detector wired into orchestrator"
```

---

### Task 5: Dry-run smoke check with synthetic OCR

**Files:**
- Test: `tests/test_ocr_integration.py`

**Interfaces:**
- Consumes: `OcrStateDetector`, `CompositeDetector`, `StateDetector`, `Orchestrator`, a fake `OcrEngine`, and `NullController`.
- Produces: nothing new — verifies the pieces work end-to-end without RapidOCR or the game.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ocr_integration.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails (or passes)**

Run: `.venv\Scripts\python -m pytest tests/test_ocr_integration.py -v`
Expected: PASS (all prior tasks complete). If it fails, the failure pinpoints
which wiring is wrong — fix before continuing.

- [ ] **Step 3: Commit**

```bash
git add tests/test_ocr_integration.py
git commit -m "test: end-to-end OCR detection drives controller"
```

---

### Task 6: Dependency + packaging

**Files:**
- Modify: `requirements.txt`
- Modify: `IEVR.spec`
- Modify: `README.md`

**Interfaces:**
- Consumes: nothing. Produces: installable + bundlable OCR backend.

- [ ] **Step 1: Add the dependency**

Append to `requirements.txt`:

```
rapidocr-onnxruntime>=1.3
```

- [ ] **Step 2: Install it**

Run: `.venv\Scripts\python -m pip install rapidocr-onnxruntime`
Expected: installs `rapidocr-onnxruntime` and `onnxruntime`.

- [ ] **Step 3: Run the full suite (now incl. real-engine test)**

Run: `.venv\Scripts\python -m pytest`
Expected: PASS, including `tests/test_ocr_engine.py::test_make_ocr_engine_returns_engine_with_read`.

- [ ] **Step 4: Bundle OCR models in the PyInstaller spec**

Open `IEVR.spec`. Find where `datas` is assembled. Add the RapidOCR package
data (models + config) using PyInstaller's collectors. Near the top of the
spec, after existing imports, add:

```python
from PyInstaller.utils.hooks import collect_data_files, collect_submodules
_rapidocr_datas = collect_data_files("rapidocr_onnxruntime")
_rapidocr_hidden = collect_submodules("rapidocr_onnxruntime") + collect_submodules("onnxruntime")
```

Then extend the existing `datas=[...]` for the bot `Analysis` with
`+ _rapidocr_datas`, and the existing `hiddenimports=[...]` with
`+ _rapidocr_hidden`. (If the spec has separate `Analysis` objects for
`IEVR.exe` and `capture_templates.exe`, only the `IEVR.exe` one needs these.)

- [ ] **Step 5: Verify the spec still parses**

Run: `.venv\Scripts\python -c "import ast; ast.parse(open('IEVR.spec').read()); print('spec ok')"`
Expected: `spec ok`

(A full `build_exe.py` run is optional here — it is slow. Do it before
distributing.)

- [ ] **Step 6: Update the README**

In `README.md`, under the detection notes, replace the template-capture-centric
guidance with: the bot now detects screens via OCR by default
(`detection: composite` in the profile); reference templates are an optional
fallback; tune `ocr.keywords` in `profiles/*.yaml` against the real screens if a
state is missed. Keep the ViGEmBus / vgamepad and background-capture sections.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt IEVR.spec README.md
git commit -m "build: add RapidOCR dependency and bundle models; update README"
```

---

## Self-Review

**Spec coverage:**
- OcrStateDetector → Task 3. CompositeDetector → Task 4. Template fallback kept → Task 4 (`build_detector`). Profile `detection`/`ocr` config → Task 1. RapidOCR engine → Task 2. Engine-init failure falls back to template-only → Task 4 `build_detector` try/except. Orchestrator wiring → Task 4 Step 5. Performance `region` → supported in `OcrStateDetector._crop` (Task 3) and config (Task 1). Tests with fake engine → Tasks 3–5. Packaging/deps → Task 6. Manual real-frame tuning → README (Task 6 Step 6). All spec sections covered.

**Placeholder scan:** No TBD/TODO; every code step shows full code. The README step describes concrete edits rather than verbatim prose, which is acceptable for docs.

**Type consistency:** All detectors expose `best_score(frame) -> (GameState, float)` and `detect(frame) -> GameState`. `OcrEngine.read(frame) -> list[str]` used consistently in Tasks 2/3/5. `build_detector(profile)` and `make_ocr_engine(lang)` signatures match across Tasks 2 and 4. Profile fields `detection`/`ocr` defined in Task 1 and consumed in Task 4. Consistent.
