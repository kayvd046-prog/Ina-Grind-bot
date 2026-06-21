# OCR-Primary State Detection (with Template Fallback)

**Date:** 2026-06-21
**Status:** Approved — ready for implementation plan

## Problem

The bot does nothing and the user has to press buttons manually. Root cause:
`templates/pve/` contains only `.gitkeep` — no reference screenshots. The
template detector (`vision.StateDetector`, `cv2.matchTemplate` at threshold
0.85) therefore always returns `UNKNOWN`, so `StateMachine.handle(UNKNOWN)`
never sends input.

The current method requires a painful manual setup: capture and crop a
reference PNG per game screen, per resolution. The user wants to move away from
this.

### Rejected alternatives

- **Game-memory reading.** Inazuma Eleven: Victory Road ships with Easy
  Anti-Cheat (EAC) via Epic Online Services. Level-5 publicly describes their
  anti-cheat as a "malicious curse" — a stealth, account-wide shadow-penalty
  triggered by cheat tools / data alteration, including read-only memory access
  (`OpenProcess`/`ReadProcessMemory`). Memory reading is the one approach that
  touches the protected process, so it is rejected. (Screen capture + virtual
  gamepad do not touch game memory and are indistinguishable to EAC from a human
  with a controller — they stay.)
- **Internet screenshots as templates.** `cv2.matchTemplate` is pixel- and
  resolution-sensitive; web images differ in resolution, JPEG compression,
  platform/language, and crop, so they will not match at threshold 0.85.

## Solution

Keep capture + gamepad unchanged (EAC-safe). Replace pixel-template detection as
the primary path with **OCR**: read on-screen text and map keywords to game
states. Keep template matching as a fallback. UI language is **English**.

### Architecture

Only the detector changes. Capture (`capture.py`) and input (`controller.py`)
are untouched.

- **`OcrStateDetector`** (new) — wraps an OCR engine; runs OCR on a frame,
  lowercases recognized text, and maps it to a `GameState` via per-state keyword
  lists from the profile. Returns `(GameState, confidence)`.
- **`StateDetector`** (existing, unchanged) — template matching, used as
  fallback.
- **`CompositeDetector`** (new) — same interface as `StateDetector`
  (`best_score(frame) -> (GameState, float)` and `detect(frame)`). Tries OCR
  first; if OCR confidence ≥ `min_confidence` and state is not `UNKNOWN`, returns
  it; otherwise delegates to the template `StateDetector`.

`orchestrator.build_orchestrator` selects the detector based on the profile's
`detection` field (`ocr` | `template` | `composite`, default `composite`) and
wires it in place of the current `StateDetector` at orchestrator.py:95.

### OCR engine

**RapidOCR (`rapidocr-onnxruntime`).** Pip-only, offline, bundles small ONNX
models (~10 MB), no separate system install — fits the standalone-exe goal.
Wrapped behind a thin interface (`detect_text(frame) -> list[str]`) so the
engine can be swapped and faked in tests.

### Config (profiles/*.yaml)

New block (keywords are an initial guess, tuned against real frames):

```yaml
detection: composite        # ocr | template | composite
ocr:
  lang: en
  min_confidence: 0.5
  region: null              # null = whole frame; can be narrowed later for speed
  keywords:
    MAIN_MENU:   ["press start", "continue", "play"]
    KICKOFF:     ["kick off", "commander"]
    HALFTIME:    ["half time"]
    GOAL:        ["goal"]
    FULLTIME:    ["full time"]
    REWARDS:     ["reward", "rewards"]
    POST_MATCH:  ["match result", "results", "next"]
    LOADING:     ["loading", "now loading"]
    ERROR_DIALOG:["error", "disconnected", "communication"]
```

`config.Profile` gains `detection: str` and `ocr: dict` fields with safe
defaults so existing profiles without the block still load.

### Detection logic

1. OCR the frame (optionally a configured `region`; downscale large frames for
   speed). Collect recognized lines, lowercase + strip.
2. For each state, in a fixed priority order, count how many of its keywords
   appear as substrings in the recognized text.
3. Pick the state with the most hits (ties broken by priority order).
4. Confidence = a normalized hit score in [0, 1]. If ≥ `min_confidence`, return
   that state; else `UNKNOWN`.
5. `CompositeDetector`: on `UNKNOWN`/low confidence, fall back to the template
   detector (which returns `UNKNOWN` when no templates exist — graceful).

### Data flow

Unchanged: `Orchestrator.step` grabs a frame → `detector.best_score(frame)` →
watchdog + statemachine → controller. Only the detector implementation swaps.

### Error handling

- If the OCR engine fails to initialize (e.g. missing model), log a warning and
  fall back to template-only detection so the bot still runs.
- Per-step OCR exceptions are caught by the existing orchestrator loop
  (orchestrator.py:60) with its back-off.

### Performance

OCR (~50–300 ms/frame) is slower than template matching but well within the
0.4 s `poll_interval`. `region` and downscaling are available if needed.

### Packaging

- Add `rapidocr-onnxruntime` to requirements.txt.
- Bundle its ONNX models via PyInstaller `datas` in IEVR.spec so IEVR.exe keeps
  working.

## Testing

- `OcrStateDetector` with a **fake** OCR engine returning canned strings:
  correct state mapping, priority tie-breaking, `UNKNOWN` below `min_confidence`.
- `CompositeDetector` with fake OCR + fake template detector: OCR wins when
  confident; template used otherwise; both `UNKNOWN` → `UNKNOWN`.
- `config` loads profiles with and without the `detection`/`ocr` block.
- Existing 25 tests stay green.
- Real-frame validation (keyword accuracy) is manual — requires the running
  game — and is documented as a tuning step after first run.

## Out of scope

- Game-memory reading.
- Internet-sourced templates.
- Any change to capture or input.
