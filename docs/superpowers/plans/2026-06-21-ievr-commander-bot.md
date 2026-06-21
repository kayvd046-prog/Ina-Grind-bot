# IEVR Commander-Mode Bot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fully autonomous Python bot (with a PySide6 GUI) that grinds *Inazuma Eleven: Victory Road* matches in the game's built-in Commander Mode by detecting on-screen states and sending controller input.

**Architecture:** A headless core (capture → vision/state-detection → state-machine → input) driven by an `Orchestrator` loop with a `Watchdog` for self-recovery. A thin PySide6 GUI runs the orchestrator in a `QThread` and shows live status, logs, and a screenshot preview. Detection uses OpenCV template matching against reference screenshots; input uses a virtual Xbox controller (`vgamepad`) with a keyboard fallback.

**Tech Stack:** Python 3.11+, `mss` (capture), `opencv-python` + `numpy` (vision), `vgamepad` (input, needs ViGEmBus), `pydirectinput` (keyboard fallback), `PyYAML` (config), `PySide6` (GUI), `pytest` (tests).

## Global Constraints

- Python 3.11+ on Windows 11.
- Target game: *Inazuma Eleven: Victory Road* on PC/Steam, same machine.
- Default profile is **PvE**; Ranked is opt-in (ToS risk noted in spec).
- Autonomy starts from the game already at the main menu; bot loops until manually stopped.
- Core logic (`ievr_bot/`) must be importable and unit-testable **without** the game running, without a real gamepad, and without a display (headless).
- Hardware/display-dependent code (`capture`, `controller`, `gui`) sits behind interfaces so the core can be tested with fakes.
- All abstract button names used by handlers must exist in every profile's `button_map`.
- Frequent commits: one per task minimum.

---

## File Structure

```
IEVR/
  ievr_bot/
    __init__.py
    states.py         # GameState enum (no deps)
    config.py         # Profile dataclass + load_profile()
    logger.py         # get_logger() + in-memory log buffer
    capture.py        # ScreenCapture (mss) behind FrameSource protocol
    vision.py         # StateDetector (template matching)
    controller.py     # InputController protocol + VGamepad/Keyboard/Null impls
    statemachine.py   # StateMachine: maps GameState -> action via controller
    watchdog.py       # Watchdog: stuck/recovery detection
    orchestrator.py   # Orchestrator: wires it all, step()/run()
  gui/
    __init__.py
    worker.py         # BotWorker(QThread) wrapping Orchestrator
    widgets.py        # StatusPanel, LogPanel, PreviewPanel
    app.py            # MainWindow
  profiles/
    pve.yaml
    ranked.yaml
  templates/
    pve/   ranked/    # reference screenshots (filled during setup)
  tools/
    capture_templates.py
  tests/
  logs/
  main.py             # headless entrypoint
  run_gui.py          # GUI entrypoint
  requirements.txt
  README.md
```

---

### Task 1: Project scaffold, dependencies, and GameState enum

**Files:**
- Create: `requirements.txt`, `ievr_bot/__init__.py`, `gui/__init__.py`, `ievr_bot/states.py`, `tests/__init__.py`, `tests/test_states.py`, `.gitignore`

**Interfaces:**
- Consumes: nothing.
- Produces: `ievr_bot.states.GameState` (Enum) with members `UNKNOWN, MAIN_MENU, LOADING, KICKOFF, IN_MATCH, FOCUS_BATTLE, HALFTIME, GOAL, FULLTIME, REWARDS, POST_MATCH, ERROR_DIALOG`. Helper `GameState.is_terminal_screen() -> bool` (True for HALFTIME, GOAL, FULLTIME, REWARDS, POST_MATCH).

- [ ] **Step 1: Create `requirements.txt`**

```text
mss>=9.0
opencv-python>=4.9
numpy>=1.26
vgamepad>=0.1.0
pydirectinput>=1.0.4
PyYAML>=6.0
PySide6>=6.6
pytest>=8.0
```

- [ ] **Step 2: Create `.gitignore`**

```text
__pycache__/
*.pyc
logs/*.log
.venv/
.pytest_cache/
templates/**/*.png
!templates/**/.gitkeep
```

- [ ] **Step 3: Create empty package files**

Create `ievr_bot/__init__.py`, `gui/__init__.py`, `tests/__init__.py` (empty files).

- [ ] **Step 4: Write the failing test** in `tests/test_states.py`

```python
from ievr_bot.states import GameState


def test_all_expected_states_exist():
    names = {s.name for s in GameState}
    assert {"UNKNOWN", "MAIN_MENU", "LOADING", "KICKOFF", "IN_MATCH",
            "FOCUS_BATTLE", "HALFTIME", "GOAL", "FULLTIME", "REWARDS",
            "POST_MATCH", "ERROR_DIALOG"} <= names


def test_terminal_screens():
    assert GameState.HALFTIME.is_terminal_screen()
    assert GameState.REWARDS.is_terminal_screen()
    assert not GameState.IN_MATCH.is_terminal_screen()
    assert not GameState.UNKNOWN.is_terminal_screen()
```

- [ ] **Step 5: Run test to verify it fails**

Run: `python -m pytest tests/test_states.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ievr_bot.states'`

- [ ] **Step 6: Implement `ievr_bot/states.py`**

```python
from enum import Enum, auto


class GameState(Enum):
    UNKNOWN = auto()
    MAIN_MENU = auto()
    LOADING = auto()
    KICKOFF = auto()
    IN_MATCH = auto()
    FOCUS_BATTLE = auto()
    HALFTIME = auto()
    GOAL = auto()
    FULLTIME = auto()
    REWARDS = auto()
    POST_MATCH = auto()
    ERROR_DIALOG = auto()

    def is_terminal_screen(self) -> bool:
        return self in {
            GameState.HALFTIME,
            GameState.GOAL,
            GameState.FULLTIME,
            GameState.REWARDS,
            GameState.POST_MATCH,
        }
```

- [ ] **Step 7: Run test to verify it passes**

Run: `python -m pytest tests/test_states.py -v`
Expected: PASS (2 passed)

- [ ] **Step 8: Commit**

```bash
git add requirements.txt .gitignore ievr_bot/ gui/__init__.py tests/
git commit -m "feat: scaffold project and GameState enum"
```

---

### Task 2: Config loader and profiles

**Files:**
- Create: `ievr_bot/config.py`, `profiles/pve.yaml`, `profiles/ranked.yaml`, `tests/test_config.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `Profile` dataclass: `name: str`, `mode: str`, `templates_dir: Path`, `button_map: dict[str, str]`, `timings: dict[str, float]`, `match_threshold: float`, `phase2_enabled: bool`.
  - `load_profile(name: str, profiles_dir: Path | None = None) -> Profile` — reads `profiles/<name>.yaml`; raises `FileNotFoundError` for unknown names and `ValueError` if a required abstract button is missing.
  - Module constant `REQUIRED_BUTTONS = ("confirm", "cancel", "commander_toggle", "menu")`.

- [ ] **Step 1: Create `profiles/pve.yaml`**

```yaml
name: pve
mode: pve
templates_subdir: pve
match_threshold: 0.85
phase2_enabled: false
button_map:
  confirm: A
  cancel: B
  commander_toggle: Y
  menu: START
timings:
  poll_interval: 0.4
  tap_cooldown: 0.6
  stuck_seconds: 25
  recovery_backoff: 2.0
```

- [ ] **Step 2: Create `profiles/ranked.yaml`**

```yaml
name: ranked
mode: ranked
templates_subdir: ranked
match_threshold: 0.85
phase2_enabled: false
button_map:
  confirm: A
  cancel: B
  commander_toggle: Y
  menu: START
timings:
  poll_interval: 0.4
  tap_cooldown: 0.6
  stuck_seconds: 40
  recovery_backoff: 3.0
```

- [ ] **Step 3: Write the failing test** in `tests/test_config.py`

```python
import pytest
from pathlib import Path
from ievr_bot.config import load_profile, Profile, REQUIRED_BUTTONS


PROFILES = Path(__file__).resolve().parents[1] / "profiles"


def test_load_pve_profile():
    p = load_profile("pve", PROFILES)
    assert isinstance(p, Profile)
    assert p.mode == "pve"
    assert p.match_threshold == 0.85
    assert p.timings["poll_interval"] == 0.4
    for b in REQUIRED_BUTTONS:
        assert b in p.button_map


def test_unknown_profile_raises():
    with pytest.raises(FileNotFoundError):
        load_profile("does_not_exist", PROFILES)


def test_missing_button_raises(tmp_path):
    (tmp_path / "bad.yaml").write_text(
        "name: bad\nmode: pve\ntemplates_subdir: pve\n"
        "match_threshold: 0.85\nphase2_enabled: false\n"
        "button_map: {confirm: A}\ntimings: {}\n"
    )
    with pytest.raises(ValueError):
        load_profile("bad", tmp_path)
```

- [ ] **Step 4: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ievr_bot.config'`

- [ ] **Step 5: Implement `ievr_bot/config.py`**

```python
from dataclasses import dataclass, field
from pathlib import Path
import yaml

REQUIRED_BUTTONS = ("confirm", "cancel", "commander_toggle", "menu")
DEFAULT_PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


@dataclass
class Profile:
    name: str
    mode: str
    templates_dir: Path
    button_map: dict
    timings: dict
    match_threshold: float = 0.85
    phase2_enabled: bool = False


def load_profile(name: str, profiles_dir: Path | None = None) -> Profile:
    base = profiles_dir or DEFAULT_PROFILES_DIR
    path = base / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {path}")
    data = yaml.safe_load(path.read_text())
    button_map = data.get("button_map", {})
    missing = [b for b in REQUIRED_BUTTONS if b not in button_map]
    if missing:
        raise ValueError(f"Profile '{name}' missing buttons: {missing}")
    templates_root = base.parent / "templates"
    return Profile(
        name=data["name"],
        mode=data["mode"],
        templates_dir=templates_root / data["templates_subdir"],
        button_map=button_map,
        timings=data.get("timings", {}),
        match_threshold=float(data.get("match_threshold", 0.85)),
        phase2_enabled=bool(data.get("phase2_enabled", False)),
    )
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (3 passed)

- [ ] **Step 7: Commit**

```bash
git add ievr_bot/config.py profiles/ tests/test_config.py
git commit -m "feat: add config loader and PvE/Ranked profiles"
```

---

### Task 3: Logger with in-memory buffer (for GUI)

**Files:**
- Create: `ievr_bot/logger.py`, `tests/test_logger.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `get_logger(name: str = "ievr") -> logging.Logger` — configured once, writes to `logs/ievr.log` and console.
  - `class BufferHandler(logging.Handler)` with `records: list[str]` and a `callback` attribute (`Callable[[str], None] | None`) invoked per formatted record. Lets the GUI subscribe to log lines.

- [ ] **Step 1: Write the failing test** in `tests/test_logger.py`

```python
import logging
from ievr_bot.logger import get_logger, BufferHandler


def test_buffer_handler_collects_and_callbacks():
    received = []
    handler = BufferHandler()
    handler.callback = received.append
    logger = logging.getLogger("test_ievr_buffer")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    logger.info("hello")

    assert any("hello" in line for line in handler.records)
    assert any("hello" in line for line in received)


def test_get_logger_returns_singleton():
    a = get_logger()
    b = get_logger()
    assert a is b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_logger.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ievr_bot.logger'`

- [ ] **Step 3: Implement `ievr_bot/logger.py`**

```python
import logging
from pathlib import Path
from typing import Callable, Optional

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_logger: Optional[logging.Logger] = None
_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


class BufferHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[str] = []
        self.callback: Optional[Callable[[str], None]] = None
        self.setFormatter(logging.Formatter(_FORMAT))

    def emit(self, record: logging.LogRecord) -> None:
        line = self.format(record)
        self.records.append(line)
        if self.callback:
            self.callback(line)


def get_logger(name: str = "ievr") -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    _LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter(_FORMAT)
    fh = logging.FileHandler(_LOG_DIR / "ievr.log", encoding="utf-8")
    fh.setFormatter(fmt)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(fh)
    logger.addHandler(ch)
    logger.buffer = BufferHandler()  # type: ignore[attr-defined]
    logger.addHandler(logger.buffer)  # type: ignore[attr-defined]
    _logger = logger
    return logger
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_logger.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add ievr_bot/logger.py tests/test_logger.py
git commit -m "feat: add logger with GUI-subscribable buffer handler"
```

---

### Task 4: Vision — StateDetector (template matching)

**Files:**
- Create: `ievr_bot/vision.py`, `tests/test_vision.py`

**Interfaces:**
- Consumes: `ievr_bot.states.GameState`.
- Produces:
  - `class StateDetector`:
    - `__init__(self, templates_dir: Path, threshold: float = 0.85)` — loads every `<state_name>.png` (lowercase enum name) it finds in `templates_dir` as a grayscale template.
    - `detect(self, frame: np.ndarray) -> GameState` — returns the `GameState` whose template has the highest match score above `threshold`, else `GameState.UNKNOWN`. `frame` is BGR (H,W,3) uint8.
    - `best_score(self, frame: np.ndarray) -> tuple[GameState, float]` — same but also returns the score (for the GUI overlay / tuning).

- [ ] **Step 1: Write the failing test** in `tests/test_vision.py`

```python
import numpy as np
import cv2
from ievr_bot.vision import StateDetector
from ievr_bot.states import GameState


def _make_templates(tmp_path):
    # main_menu template: a white box top-left
    menu = np.zeros((40, 40, 3), np.uint8)
    menu[5:20, 5:20] = 255
    cv2.imwrite(str(tmp_path / "main_menu.png"), menu)
    # kickoff template: a white box bottom-right
    kick = np.zeros((40, 40, 3), np.uint8)
    kick[20:35, 20:35] = 255
    cv2.imwrite(str(tmp_path / "kickoff.png"), kick)
    return tmp_path


def test_detect_matches_correct_state(tmp_path):
    _make_templates(tmp_path)
    det = StateDetector(tmp_path, threshold=0.8)
    # Frame contains the kickoff pattern in a larger image
    frame = np.zeros((100, 100, 3), np.uint8)
    frame[60:75, 60:75] = 255
    assert det.detect(frame) == GameState.KICKOFF


def test_detect_returns_unknown_when_no_match(tmp_path):
    _make_templates(tmp_path)
    det = StateDetector(tmp_path, threshold=0.95)
    frame = np.full((100, 100, 3), 128, np.uint8)  # flat gray, no pattern
    assert det.detect(frame) == GameState.UNKNOWN
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vision.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ievr_bot.vision'`

- [ ] **Step 3: Implement `ievr_bot/vision.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_vision.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add ievr_bot/vision.py tests/test_vision.py
git commit -m "feat: add template-matching StateDetector"
```

---

### Task 5: Input controller (protocol + impls)

**Files:**
- Create: `ievr_bot/controller.py`, `tests/test_controller.py`

**Interfaces:**
- Consumes: `Profile.button_map`.
- Produces:
  - `class InputController(Protocol)`: `press(self, button: str, duration: float = 0.1) -> None`.
  - `class NullController` — records calls in `self.presses: list[str]` (abstract button names); used in tests and dry-run.
  - `class VGamepadController(button_map: dict)` — maps abstract names → `vgamepad` Xbox buttons, presses+releases with `duration`. Imports `vgamepad` lazily inside `__init__` so the module imports without the driver.
  - `class KeyboardController(button_map: dict)` — maps abstract names → keyboard keys via `pydirectinput`, lazy import.
  - `make_controller(kind: str, button_map: dict) -> InputController` where `kind in {"null", "vgamepad", "keyboard"}`.

- [ ] **Step 1: Write the failing test** in `tests/test_controller.py`

```python
import pytest
from ievr_bot.controller import NullController, make_controller


def test_null_controller_records_presses():
    c = NullController()
    c.press("confirm")
    c.press("commander_toggle", duration=0.2)
    assert c.presses == ["confirm", "commander_toggle"]


def test_make_controller_null():
    c = make_controller("null", {"confirm": "A"})
    assert isinstance(c, NullController)


def test_make_controller_unknown_kind():
    with pytest.raises(ValueError):
        make_controller("bogus", {})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_controller.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ievr_bot.controller'`

- [ ] **Step 3: Implement `ievr_bot/controller.py`**

```python
import time
from typing import Protocol, runtime_checkable


@runtime_checkable
class InputController(Protocol):
    def press(self, button: str, duration: float = 0.1) -> None: ...


class NullController:
    def __init__(self) -> None:
        self.presses: list[str] = []

    def press(self, button: str, duration: float = 0.1) -> None:
        self.presses.append(button)


class VGamepadController:
    def __init__(self, button_map: dict) -> None:
        import vgamepad as vg
        self._vg = vg
        self.pad = vg.VX360Gamepad()
        self.button_map = button_map
        self._lookup = {
            "A": vg.XUSB_BUTTON.XUSB_GAMEPAD_A,
            "B": vg.XUSB_BUTTON.XUSB_GAMEPAD_B,
            "X": vg.XUSB_BUTTON.XUSB_GAMEPAD_X,
            "Y": vg.XUSB_BUTTON.XUSB_GAMEPAD_Y,
            "START": vg.XUSB_BUTTON.XUSB_GAMEPAD_START,
            "LB": vg.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER,
            "RB": vg.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER,
        }

    def press(self, button: str, duration: float = 0.1) -> None:
        key = self.button_map[button]
        btn = self._lookup[key]
        self.pad.press_button(btn)
        self.pad.update()
        time.sleep(duration)
        self.pad.release_button(btn)
        self.pad.update()


class KeyboardController:
    def __init__(self, button_map: dict) -> None:
        import pydirectinput
        self._kb = pydirectinput
        self.button_map = button_map

    def press(self, button: str, duration: float = 0.1) -> None:
        key = self.button_map[button]
        self._kb.keyDown(key)
        time.sleep(duration)
        self._kb.keyUp(key)


def make_controller(kind: str, button_map: dict) -> InputController:
    if kind == "null":
        return NullController()
    if kind == "vgamepad":
        return VGamepadController(button_map)
    if kind == "keyboard":
        return KeyboardController(button_map)
    raise ValueError(f"Unknown controller kind: {kind}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_controller.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add ievr_bot/controller.py tests/test_controller.py
git commit -m "feat: add input controller protocol with vgamepad/keyboard/null impls"
```

---

### Task 6: State machine (per-state actions)

**Files:**
- Create: `ievr_bot/statemachine.py`, `tests/test_statemachine.py`

**Interfaces:**
- Consumes: `GameState`, `InputController`, `Profile`.
- Produces:
  - `class StateMachine(profile: Profile, controller: InputController)`:
    - `handle(self, state: GameState) -> str` — performs the action for `state`, returns a short human-readable description of what it did. Tracks `self.matches_completed: int` (incremented when a POST_MATCH is handled after an in-match phase).
    - Behavior: `KICKOFF` → press `commander_toggle` then `confirm`; terminal screens (`HALFTIME/GOAL/FULLTIME/REWARDS/POST_MATCH`) → press `confirm`; `MAIN_MENU`/`POST_MATCH` → press `confirm` to (re)start a match; `ERROR_DIALOG` → press `cancel`; `IN_MATCH`/`LOADING`/`UNKNOWN` → no input.
    - `POST_MATCH` increments `matches_completed`.

- [ ] **Step 1: Write the failing test** in `tests/test_statemachine.py`

```python
from ievr_bot.statemachine import StateMachine
from ievr_bot.controller import NullController
from ievr_bot.config import Profile
from ievr_bot.states import GameState
from pathlib import Path


def _profile():
    return Profile(
        name="t", mode="pve", templates_dir=Path("."),
        button_map={"confirm": "A", "cancel": "B",
                    "commander_toggle": "Y", "menu": "START"},
        timings={}, match_threshold=0.85, phase2_enabled=False,
    )


def test_kickoff_enables_commander_mode():
    c = NullController()
    sm = StateMachine(_profile(), c)
    sm.handle(GameState.KICKOFF)
    assert "commander_toggle" in c.presses


def test_terminal_screen_presses_confirm():
    c = NullController()
    sm = StateMachine(_profile(), c)
    sm.handle(GameState.REWARDS)
    assert c.presses == ["confirm"]


def test_in_match_sends_no_input():
    c = NullController()
    sm = StateMachine(_profile(), c)
    sm.handle(GameState.IN_MATCH)
    assert c.presses == []


def test_error_dialog_presses_cancel():
    c = NullController()
    sm = StateMachine(_profile(), c)
    sm.handle(GameState.ERROR_DIALOG)
    assert c.presses == ["cancel"]


def test_post_match_increments_counter():
    c = NullController()
    sm = StateMachine(_profile(), c)
    assert sm.matches_completed == 0
    sm.handle(GameState.POST_MATCH)
    assert sm.matches_completed == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_statemachine.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ievr_bot.statemachine'`

- [ ] **Step 3: Implement `ievr_bot/statemachine.py`**

```python
from .states import GameState
from .config import Profile
from .controller import InputController


class StateMachine:
    def __init__(self, profile: Profile, controller: InputController) -> None:
        self.profile = profile
        self.controller = controller
        self.matches_completed = 0

    def handle(self, state: GameState) -> str:
        if state == GameState.KICKOFF:
            self.controller.press("commander_toggle")
            self.controller.press("confirm")
            return "kickoff: enabled commander mode"
        if state == GameState.POST_MATCH:
            self.matches_completed += 1
            self.controller.press("confirm")
            return "post-match: advancing, starting next match"
        if state == GameState.MAIN_MENU:
            self.controller.press("confirm")
            return "main menu: starting match"
        if state.is_terminal_screen():
            self.controller.press("confirm")
            return f"{state.name.lower()}: confirm"
        if state == GameState.ERROR_DIALOG:
            self.controller.press("cancel")
            return "error dialog: dismissed"
        return f"{state.name.lower()}: waiting"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_statemachine.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add ievr_bot/statemachine.py tests/test_statemachine.py
git commit -m "feat: add state machine mapping game states to controller actions"
```

---

### Task 7: Watchdog (stuck detection + recovery)

**Files:**
- Create: `ievr_bot/watchdog.py`, `tests/test_watchdog.py`

**Interfaces:**
- Consumes: `GameState`.
- Produces:
  - `class Watchdog(stuck_seconds: float, now: Callable[[], float] = time.monotonic)`:
    - `update(self, state: GameState) -> None` — records state; resets the timer when the state changes.
    - `seconds_in_state(self) -> float`.
    - `is_stuck(self) -> bool` — True when `seconds_in_state() >= stuck_seconds` AND state is `UNKNOWN` or unchanged.
    - `consecutive_recoveries: int` and `note_recovery() / reset_recoveries()`.

- [ ] **Step 1: Write the failing test** in `tests/test_watchdog.py`

```python
from ievr_bot.watchdog import Watchdog
from ievr_bot.states import GameState


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_timer_resets_on_state_change():
    clk = FakeClock()
    wd = Watchdog(stuck_seconds=10, now=clk)
    wd.update(GameState.IN_MATCH)
    clk.t = 5
    assert wd.seconds_in_state() == 5
    wd.update(GameState.HALFTIME)  # change resets
    assert wd.seconds_in_state() == 0


def test_is_stuck_after_threshold():
    clk = FakeClock()
    wd = Watchdog(stuck_seconds=10, now=clk)
    wd.update(GameState.UNKNOWN)
    clk.t = 9
    assert not wd.is_stuck()
    clk.t = 11
    assert wd.is_stuck()


def test_recovery_counter():
    wd = Watchdog(stuck_seconds=10)
    wd.note_recovery()
    wd.note_recovery()
    assert wd.consecutive_recoveries == 2
    wd.reset_recoveries()
    assert wd.consecutive_recoveries == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_watchdog.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ievr_bot.watchdog'`

- [ ] **Step 3: Implement `ievr_bot/watchdog.py`**

```python
import time
from typing import Callable
from .states import GameState


class Watchdog:
    def __init__(self, stuck_seconds: float,
                 now: Callable[[], float] = time.monotonic) -> None:
        self.stuck_seconds = stuck_seconds
        self._now = now
        self._state: GameState | None = None
        self._since = now()
        self.consecutive_recoveries = 0

    def update(self, state: GameState) -> None:
        if state != self._state:
            self._state = state
            self._since = self._now()

    def seconds_in_state(self) -> float:
        return self._now() - self._since

    def is_stuck(self) -> bool:
        return self.seconds_in_state() >= self.stuck_seconds

    def note_recovery(self) -> None:
        self.consecutive_recoveries += 1

    def reset_recoveries(self) -> None:
        self.consecutive_recoveries = 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_watchdog.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add ievr_bot/watchdog.py tests/test_watchdog.py
git commit -m "feat: add watchdog for stuck detection and recovery counting"
```

---

### Task 8: Capture module (mss) behind a FrameSource

**Files:**
- Create: `ievr_bot/capture.py`, `tests/test_capture.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `class FrameSource(Protocol)`: `grab(self) -> np.ndarray` (BGR uint8).
  - `class ScreenCapture(region: dict | None = None)` — uses `mss`; `grab()` returns the primary monitor (or `region={'top','left','width','height'}`) as BGR. Lazy-imports `mss`.
  - `class StaticFrameSource(frame: np.ndarray)` — returns a fixed frame; for tests/dry-run replays.

- [ ] **Step 1: Write the failing test** in `tests/test_capture.py`

```python
import numpy as np
from ievr_bot.capture import StaticFrameSource


def test_static_frame_source_returns_frame():
    frame = np.zeros((10, 10, 3), np.uint8)
    src = StaticFrameSource(frame)
    out = src.grab()
    assert out.shape == (10, 10, 3)
    assert np.array_equal(out, frame)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_capture.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ievr_bot.capture'`

- [ ] **Step 3: Implement `ievr_bot/capture.py`**

```python
from typing import Protocol
import numpy as np


class FrameSource(Protocol):
    def grab(self) -> np.ndarray: ...


class StaticFrameSource:
    def __init__(self, frame: np.ndarray) -> None:
        self._frame = frame

    def grab(self) -> np.ndarray:
        return self._frame


class ScreenCapture:
    def __init__(self, region: dict | None = None) -> None:
        import mss
        self._sct = mss.mss()
        self.region = region or self._sct.monitors[1]

    def grab(self) -> np.ndarray:
        shot = self._sct.grab(self.region)
        arr = np.array(shot)  # BGRA
        return arr[:, :, :3]  # drop alpha -> BGR
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_capture.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add ievr_bot/capture.py tests/test_capture.py
git commit -m "feat: add capture module with mss and static test source"
```

---

### Task 9: Orchestrator (wire everything + step/run)

**Files:**
- Create: `ievr_bot/orchestrator.py`, `main.py`, `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `FrameSource`, `StateDetector`, `StateMachine`, `Watchdog`, `Profile`.
- Produces:
  - `@dataclass StatusUpdate`: `state: GameState`, `score: float`, `action: str`, `matches: int`, `frame: np.ndarray | None`.
  - `class Orchestrator(source, detector, machine, watchdog, profile, dry_run=False, on_update=None)`:
    - `step(self) -> StatusUpdate` — one cycle: grab → detect → (if stuck) recovery (press `cancel`, `note_recovery`) → else `machine.handle(state)` → build `StatusUpdate`, call `on_update`, return it. In `dry_run`, never calls controller (machine is given a `NullController` by the caller).
    - `run(self, stop_event) -> None` — loop calling `step()` then sleeping `poll_interval`, until `stop_event.is_set()`.
  - `build_orchestrator(profile, controller_kind="vgamepad", dry_run=False, source=None, on_update=None) -> Orchestrator` — factory wiring real components (used by `main.py` and GUI).

- [ ] **Step 1: Write the failing test** in `tests/test_orchestrator.py`

```python
import numpy as np
from pathlib import Path
from ievr_bot.orchestrator import Orchestrator
from ievr_bot.capture import StaticFrameSource
from ievr_bot.statemachine import StateMachine
from ievr_bot.controller import NullController
from ievr_bot.watchdog import Watchdog
from ievr_bot.config import Profile
from ievr_bot.states import GameState


class FakeDetector:
    def __init__(self, state):
        self.state = state

    def best_score(self, frame):
        return (self.state, 0.99)


def _profile():
    return Profile(name="t", mode="pve", templates_dir=Path("."),
                   button_map={"confirm": "A", "cancel": "B",
                               "commander_toggle": "Y", "menu": "START"},
                   timings={"poll_interval": 0.0, "stuck_seconds": 10},
                   match_threshold=0.85, phase2_enabled=False)


def _orch(state, dry_run=False):
    p = _profile()
    c = NullController()
    src = StaticFrameSource(np.zeros((20, 20, 3), np.uint8))
    sm = StateMachine(p, c)
    wd = Watchdog(stuck_seconds=10, now=lambda: 0.0)
    o = Orchestrator(src, FakeDetector(state), sm, wd, p, dry_run=dry_run)
    return o, c


def test_step_returns_status_and_acts():
    o, c = _orch(GameState.KICKOFF)
    upd = o.step()
    assert upd.state == GameState.KICKOFF
    assert "commander_toggle" in c.presses
    assert upd.score == 0.99


def test_dry_run_sends_no_input():
    o, c = _orch(GameState.KICKOFF, dry_run=True)
    o.step()
    assert c.presses == []


def test_on_update_callback_called():
    p = _profile()
    src = StaticFrameSource(np.zeros((20, 20, 3), np.uint8))
    sm = StateMachine(p, NullController())
    wd = Watchdog(stuck_seconds=10, now=lambda: 0.0)
    seen = []
    o = Orchestrator(src, FakeDetector(GameState.IN_MATCH), sm, wd, p,
                     on_update=seen.append)
    o.step()
    assert len(seen) == 1 and seen[0].state == GameState.IN_MATCH
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ievr_bot.orchestrator'`

- [ ] **Step 3: Implement `ievr_bot/orchestrator.py`**

```python
import time
from dataclasses import dataclass
from typing import Callable, Optional
import numpy as np
from .states import GameState
from .config import Profile
from .logger import get_logger


@dataclass
class StatusUpdate:
    state: GameState
    score: float
    action: str
    matches: int
    frame: Optional[np.ndarray] = None


class Orchestrator:
    def __init__(self, source, detector, machine, watchdog, profile: Profile,
                 dry_run: bool = False,
                 on_update: Optional[Callable[[StatusUpdate], None]] = None) -> None:
        self.source = source
        self.detector = detector
        self.machine = machine
        self.watchdog = watchdog
        self.profile = profile
        self.dry_run = dry_run
        self.on_update = on_update
        self.log = get_logger()

    def step(self) -> StatusUpdate:
        frame = self.source.grab()
        state, score = self.detector.best_score(frame)
        self.watchdog.update(state)

        if self.watchdog.is_stuck():
            self.watchdog.note_recovery()
            action = "recovery: stuck, pressing cancel"
            if not self.dry_run:
                self.machine.controller.press("cancel")
            self.log.warning(action)
        elif self.dry_run:
            action = f"dry-run: would handle {state.name.lower()}"
        else:
            action = self.machine.handle(state)

        upd = StatusUpdate(state=state, score=score, action=action,
                           matches=self.machine.matches_completed, frame=frame)
        if self.on_update:
            self.on_update(upd)
        return upd

    def run(self, stop_event) -> None:
        interval = float(self.profile.timings.get("poll_interval", 0.4))
        self.log.info("Bot started (profile=%s, dry_run=%s)",
                      self.profile.name, self.dry_run)
        while not stop_event.is_set():
            try:
                self.step()
            except Exception:  # never let the unattended loop die
                self.log.exception("Error in step; backing off")
                time.sleep(float(self.profile.timings.get("recovery_backoff", 2.0)))
            time.sleep(interval)
        self.log.info("Bot stopped")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Add `build_orchestrator` factory to `ievr_bot/orchestrator.py`**

```python
def build_orchestrator(profile: Profile, controller_kind: str = "vgamepad",
                       dry_run: bool = False, source=None,
                       on_update=None) -> "Orchestrator":
    from .capture import ScreenCapture
    from .vision import StateDetector
    from .controller import make_controller
    from .statemachine import StateMachine
    from .watchdog import Watchdog

    src = source or ScreenCapture()
    detector = StateDetector(profile.templates_dir, profile.match_threshold)
    kind = "null" if dry_run else controller_kind
    controller = make_controller(kind, profile.button_map)
    machine = StateMachine(profile, controller)
    watchdog = Watchdog(float(profile.timings.get("stuck_seconds", 25)))
    return Orchestrator(src, detector, machine, watchdog, profile,
                        dry_run=dry_run, on_update=on_update)
```

- [ ] **Step 6: Implement `main.py` (headless entrypoint)**

```python
import argparse
import threading
from ievr_bot.config import load_profile
from ievr_bot.orchestrator import build_orchestrator


def main() -> None:
    ap = argparse.ArgumentParser(description="IEVR Commander-Mode bot (headless)")
    ap.add_argument("--profile", default="pve")
    ap.add_argument("--controller", default="vgamepad",
                    choices=["vgamepad", "keyboard"])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    profile = load_profile(args.profile)
    orch = build_orchestrator(profile, args.controller, args.dry_run)
    stop = threading.Event()
    try:
        orch.run(stop)
    except KeyboardInterrupt:
        stop.set()


if __name__ == "__main__":
    main()
```

- [ ] **Step 7: Run tests + smoke-check dry-run import**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: PASS (3 passed)
Run: `python -c "import main; import ievr_bot.orchestrator"`
Expected: no error.

- [ ] **Step 8: Commit**

```bash
git add ievr_bot/orchestrator.py main.py tests/test_orchestrator.py
git commit -m "feat: add orchestrator loop, factory, and headless entrypoint"
```

---

### Task 10: Template-capture tool

**Files:**
- Create: `tools/capture_templates.py`, `templates/pve/.gitkeep`, `templates/ranked/.gitkeep`

**Interfaces:**
- Consumes: `ScreenCapture`.
- Produces: a CLI that, on each ENTER, saves the current screen to `templates/<profile>/<state>.png`. Used during setup; no automated test (interactive, hardware-dependent) — verified manually.

- [ ] **Step 1: Create `templates/pve/.gitkeep` and `templates/ranked/.gitkeep`** (empty files).

- [ ] **Step 2: Implement `tools/capture_templates.py`**

```python
"""Interactive helper to capture reference screenshots for state detection.

Usage: python tools/capture_templates.py --profile pve
For each state, position the game on that screen, then press ENTER to save.
Press 's' then ENTER to skip a state, 'q' then ENTER to quit.
"""
import argparse
from pathlib import Path
import cv2
from ievr_bot.capture import ScreenCapture
from ievr_bot.states import GameState

CAPTURE_STATES = [
    GameState.MAIN_MENU, GameState.LOADING, GameState.KICKOFF,
    GameState.IN_MATCH, GameState.HALFTIME, GameState.GOAL,
    GameState.FULLTIME, GameState.REWARDS, GameState.POST_MATCH,
    GameState.ERROR_DIALOG,
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="pve")
    args = ap.parse_args()
    out = Path(__file__).resolve().parent.parent / "templates" / args.profile
    out.mkdir(parents=True, exist_ok=True)
    cap = ScreenCapture()

    for state in CAPTURE_STATES:
        name = state.name.lower()
        choice = input(f"Show '{name}' screen, ENTER to save "
                       f"(s=skip, q=quit): ").strip().lower()
        if choice == "q":
            break
        if choice == "s":
            continue
        frame = cap.grab()
        path = out / f"{name}.png"
        cv2.imwrite(str(path), frame)
        print(f"  saved {path}")
    print("Done. Tip: crop the saved PNGs to the distinctive UI element only.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Smoke-check it imports**

Run: `python -c "import tools.capture_templates"`
Expected: no error (note: running it fully needs a display/game; import is enough here).

- [ ] **Step 4: Commit**

```bash
git add tools/capture_templates.py templates/pve/.gitkeep templates/ranked/.gitkeep
git commit -m "feat: add interactive template-capture tool"
```

---

### Task 11: GUI worker thread

**Files:**
- Create: `gui/worker.py`, `tests/test_gui_worker.py`

**Interfaces:**
- Consumes: `build_orchestrator`, `StatusUpdate`.
- Produces:
  - `class BotWorker(QThread)`:
    - Constructor: `BotWorker(profile, controller_kind, dry_run)`.
    - Signals: `status = Signal(object)` (emits `StatusUpdate`), `log_line = Signal(str)`, `stopped = Signal()`.
    - `run(self)` — builds the orchestrator with `on_update=self.status.emit`, subscribes the logger buffer's callback to `self.log_line.emit`, runs until `stop()`.
    - `stop(self)` — sets the internal `threading.Event` and waits.

- [ ] **Step 1: Write the failing test** in `tests/test_gui_worker.py`

```python
import importlib.util
import pytest

pytest.importorskip("PySide6")


def test_bot_worker_constructs():
    from ievr_bot.config import load_profile
    from pathlib import Path
    from gui.worker import BotWorker
    profiles = Path(__file__).resolve().parents[1] / "profiles"
    profile = load_profile("pve", profiles)
    w = BotWorker(profile, controller_kind="null", dry_run=True)
    assert hasattr(w, "status")
    assert hasattr(w, "log_line")
    assert callable(w.stop)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_gui_worker.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gui.worker'`

- [ ] **Step 3: Implement `gui/worker.py`**

```python
import threading
from PySide6.QtCore import QThread, Signal
from ievr_bot.orchestrator import build_orchestrator
from ievr_bot.logger import get_logger


class BotWorker(QThread):
    status = Signal(object)
    log_line = Signal(str)
    stopped = Signal()

    def __init__(self, profile, controller_kind="vgamepad", dry_run=False):
        super().__init__()
        self.profile = profile
        self.controller_kind = controller_kind
        self.dry_run = dry_run
        self._stop = threading.Event()

    def run(self):
        logger = get_logger()
        logger.buffer.callback = self.log_line.emit  # type: ignore[attr-defined]
        orch = build_orchestrator(
            self.profile, self.controller_kind, self.dry_run,
            on_update=self.status.emit,
        )
        orch.run(self._stop)
        self.stopped.emit()

    def stop(self):
        self._stop.set()
        self.wait(5000)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_gui_worker.py -v`
Expected: PASS (1 passed) — or SKIPPED if PySide6 not yet installed; install with `pip install PySide6` then it must PASS.

- [ ] **Step 5: Commit**

```bash
git add gui/worker.py tests/test_gui_worker.py
git commit -m "feat: add QThread bot worker bridging orchestrator to Qt signals"
```

---

### Task 12: GUI widgets and main window

**Files:**
- Create: `gui/widgets.py`, `gui/app.py`, `run_gui.py`

**Interfaces:**
- Consumes: `BotWorker`, `StatusUpdate`, `load_profile`.
- Produces:
  - `gui/widgets.py`: `StatusPanel` (labels: state, score, matches, last action; method `update_status(upd: StatusUpdate)`), `LogPanel` (read-only text area; `append(line: str)`), `PreviewPanel` (`QLabel` showing the frame; `update_frame(frame)` converts BGR ndarray → `QImage`/`QPixmap`).
  - `gui/app.py`: `MainWindow` with profile dropdown (pve/ranked), controller dropdown (vgamepad/keyboard/null), dry-run checkbox, Start/Stop buttons, the three panels, dark stylesheet; wires `BotWorker` signals to panels.
  - `run_gui.py`: creates `QApplication`, shows `MainWindow`.

- [ ] **Step 1: Implement `gui/widgets.py`**

```python
import numpy as np
from PySide6.QtWidgets import QGroupBox, QLabel, QVBoxLayout, QPlainTextEdit
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtCore import Qt


class StatusPanel(QGroupBox):
    def __init__(self):
        super().__init__("Status")
        self.state = QLabel("state: -")
        self.score = QLabel("score: -")
        self.matches = QLabel("matches: 0")
        self.action = QLabel("action: -")
        lay = QVBoxLayout(self)
        for w in (self.state, self.score, self.matches, self.action):
            lay.addWidget(w)

    def update_status(self, upd):
        self.state.setText(f"state: {upd.state.name}")
        self.score.setText(f"score: {upd.score:.2f}")
        self.matches.setText(f"matches: {upd.matches}")
        self.action.setText(f"action: {upd.action}")


class LogPanel(QGroupBox):
    def __init__(self):
        super().__init__("Log")
        self.text = QPlainTextEdit(readOnly=True)
        self.text.setMaximumBlockCount(500)
        lay = QVBoxLayout(self)
        lay.addWidget(self.text)

    def append(self, line: str):
        self.text.appendPlainText(line)


class PreviewPanel(QGroupBox):
    def __init__(self):
        super().__init__("Preview")
        self.label = QLabel("no frame")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setMinimumSize(320, 180)
        lay = QVBoxLayout(self)
        lay.addWidget(self.label)

    def update_frame(self, frame: np.ndarray):
        if frame is None:
            return
        rgb = frame[:, :, ::-1].copy()  # BGR -> RGB
        h, w, _ = rgb.shape
        img = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(img).scaled(
            self.label.width(), self.label.height(),
            Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.label.setPixmap(pix)
```

- [ ] **Step 2: Implement `gui/app.py`**

```python
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QComboBox, QCheckBox, QLabel,
)
from ievr_bot.config import load_profile
from gui.worker import BotWorker
from gui.widgets import StatusPanel, LogPanel, PreviewPanel

DARK_QSS = """
QWidget { background:#1e1f22; color:#e6e6e6; font-size:13px; }
QGroupBox { border:1px solid #3a3b3f; border-radius:6px; margin-top:10px; }
QGroupBox::title { subcontrol-origin: margin; left:8px; padding:0 4px; }
QPushButton { background:#3a6df0; border:none; padding:8px 14px; border-radius:6px; }
QPushButton:disabled { background:#444; }
QPlainTextEdit { background:#141517; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IEVR Commander Bot")
        self.worker: BotWorker | None = None

        self.profile_box = QComboBox(); self.profile_box.addItems(["pve", "ranked"])
        self.controller_box = QComboBox()
        self.controller_box.addItems(["vgamepad", "keyboard", "null"])
        self.dry_run = QCheckBox("Dry-run (no input)")
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop"); self.stop_btn.setEnabled(False)

        self.status_panel = StatusPanel()
        self.log_panel = LogPanel()
        self.preview_panel = PreviewPanel()

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Profile:")); controls.addWidget(self.profile_box)
        controls.addWidget(QLabel("Input:")); controls.addWidget(self.controller_box)
        controls.addWidget(self.dry_run)
        controls.addStretch()
        controls.addWidget(self.start_btn); controls.addWidget(self.stop_btn)

        body = QHBoxLayout()
        left = QVBoxLayout(); left.addWidget(self.status_panel); left.addWidget(self.preview_panel)
        body.addLayout(left, 1); body.addWidget(self.log_panel, 1)

        root = QVBoxLayout(); root.addLayout(controls); root.addLayout(body)
        container = QWidget(); container.setLayout(root)
        self.setCentralWidget(container)
        self.setStyleSheet(DARK_QSS)

        self.start_btn.clicked.connect(self.start)
        self.stop_btn.clicked.connect(self.stop)

    def start(self):
        profiles = Path(__file__).resolve().parents[1] / "profiles"
        profile = load_profile(self.profile_box.currentText(), profiles)
        self.worker = BotWorker(
            profile, self.controller_box.currentText(), self.dry_run.isChecked())
        self.worker.status.connect(self._on_status)
        self.worker.log_line.connect(self.log_panel.append)
        self.worker.stopped.connect(self._on_stopped)
        self.worker.start()
        self.start_btn.setEnabled(False); self.stop_btn.setEnabled(True)

    def stop(self):
        if self.worker:
            self.worker.stop()

    def _on_status(self, upd):
        self.status_panel.update_status(upd)
        self.preview_panel.update_frame(upd.frame)

    def _on_stopped(self):
        self.start_btn.setEnabled(True); self.stop_btn.setEnabled(False)
```

- [ ] **Step 3: Implement `run_gui.py`**

```python
import sys
from PySide6.QtWidgets import QApplication
from gui.app import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    win = MainWindow()
    win.resize(900, 540)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Smoke-check imports**

Run: `python -c "import gui.widgets, gui.app, run_gui"`
Expected: no error (requires `pip install PySide6`).

- [ ] **Step 5: Manual check (offscreen render)**

Run: `set QT_QPA_PLATFORM=offscreen && python -c "from PySide6.QtWidgets import QApplication; from gui.app import MainWindow; app=QApplication([]); MainWindow().show(); print('GUI OK')"`
Expected: prints `GUI OK` with no exception.

- [ ] **Step 6: Commit**

```bash
git add gui/widgets.py gui/app.py run_gui.py
git commit -m "feat: add PySide6 GUI (status, log, preview, controls)"
```

---

### Task 13: README and setup guide

**Files:**
- Create: `README.md`

**Interfaces:** none (documentation).

- [ ] **Step 1: Write `README.md`**

````markdown
# IEVR Commander-Mode Bot

Autonomous bot that grinds *Inazuma Eleven: Victory Road* matches using the
game's built-in **Commander Mode**. The game's AI plays; the bot detects screens
and presses buttons to loop matches forever. See the design spec in
`docs/superpowers/specs/`.

## One-time setup

1. Install Python 3.11+.
2. `pip install -r requirements.txt`
3. Install **ViGEmBus** driver (required by `vgamepad`):
   https://github.com/ViGEm/ViGEmBus/releases
4. Launch the game, set a **fixed resolution / borderless window**.
5. Capture reference screenshots:
   `python tools/capture_templates.py --profile pve`
   Then crop each saved PNG in `templates/pve/` down to the distinctive UI
   element for that screen (button, banner, dialog).

## Run

GUI: `python run_gui.py`
Headless: `python main.py --profile pve` (add `--dry-run` to observe without
sending input, `--controller keyboard` to use the keyboard fallback).

Start the game and leave it at the main menu, then press **Start** in the GUI.

## Tests

`python -m pytest -v`

## Notes

- Start with **PvE**. Automating online Ranked may violate the game's ToS.
- Tune `match_threshold` and `timings` in `profiles/*.yaml` if detection is
  flaky.
````

- [ ] **Step 2: Run full test suite**

Run: `python -m pytest -v`
Expected: all tests PASS (GUI tests pass if PySide6 installed, else skipped).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add README with setup and run instructions"
```

---

## Self-Review

**Spec coverage check:**
- Capture → Task 8. Vision/template matching → Task 4. Controller (vgamepad + keyboard fallback) → Task 5. States + handlers → Tasks 1, 6. Orchestrator loop → Task 9. Watchdog/self-recovery → Tasks 7, 9. Config/profiles (PvE+Ranked) → Task 2. Logger → Task 3. Template-capture tool → Task 10. GUI (worker + window + panels, dark theme) → Tasks 11, 12. Dry-run mode → Tasks 9, 12. Headless `main.py` + `run_gui.py` → Tasks 9, 12. README/setup → Task 13. Tests (vision golden images, state-machine with fake controller, watchdog, orchestrator with fakes) → throughout. ✅
- Phase 2 (Focus-Battle intervention): `FOCUS_BATTLE` state and `phase2_enabled` flag are in place (Tasks 1, 2), but intervention logic is intentionally **not** implemented here — it is the next plan after Phase 1 is validated against the real game. Noted as deferred, consistent with the spec's phasing.

**Placeholder scan:** No TBD/TODO; every code step contains full code. ✅

**Type consistency:** `best_score()` returns `(GameState, float)` and is used that way in the orchestrator and FakeDetector. `StatusUpdate` fields match GUI usage. `button_map` abstract names (`confirm/cancel/commander_toggle/menu`) are consistent across config, controller, and state machine. `BotWorker` signals (`status/log_line/stopped`) match `app.py` connections. ✅
