# Record-and-extract templates — design

## Problem

Reference templates are currently captured with `tools/capture_templates.py`: an
interactive CLI that, for each game state, requires positioning the game on that
screen and pressing ENTER in the command prompt. The prompt overlaps the game,
which makes the workflow awkward. Templates are only a *fallback* for the OCR
detector (`detection: composite`), but they still need to be easy to produce.

## Goal

Replace the prompt-driven capture with a flow where the bot **records one match
by itself** (no external screen recorder, no prompt overlap), then
**auto-labels** the frames with the existing detector and lets the user
**review + crop** the chosen templates inside the GUI. OCR detection is
unchanged; this only makes the fallback templates easier to produce.

Decisions made during brainstorming:
- Recording source: the bot records itself via the profile's frame source.
- Labeling: OCR auto-labels, then a short review corrects edge cases.
- Review location: a new tab in the existing PySide6 GUI.
- Cropping: OCR proposes a crop region (from the matched text box); user refines.

## Architecture

### New, headless (no Qt) — unit-testable

- **`ievr_bot/recorder.py` — `MatchRecorder`**
  Reuses the *same* frame source the orchestrator builds (`WindowCapture` for
  `capture_backend: window`, else `ScreenCapture`). Grabs frames on an interval
  into an in-memory list of `(timestamp, frame)` until a stop event is set or a
  frame cap is hit.
  - `record(stop_event, on_frame=None) -> list[RecordedFrame]`
  - Interval from `profile.timings["poll_interval"]` (default 0.4s).
  - Frame cap (default e.g. 4000) bounds memory; a 5-min match at ~2.5fps is
    well under that. On cap, recording stops with a logged note.
  - Grab errors are caught per-iteration (logged, skipped) so a transient
    window-gone/black-frame does not abort the whole recording. Mirrors the
    orchestrator's resilience.

- **`ievr_bot/template_extractor.py` — `extract_candidates`**
  Pure function over recorded frames.
  - `extract_candidates(frames, detector, ocr_engine, top_n=5) ->
    dict[GameState, list[Candidate]]`
  - For each frame, ask `detector.best_score(frame)`; group frames by the
    detected `GameState` (ignoring `UNKNOWN`).
  - Per state, keep the `top_n` frames by score (descending).
  - For each candidate, derive a **proposed crop box** from `ocr_engine`'s text
    boxes: the union of boxes whose text matches that state's keywords, padded
    and clamped to frame bounds. If no box matches, propose `None` (review shows
    the full frame and the user draws one).
  - `Candidate` dataclass: `frame: np.ndarray`, `score: float`,
    `crop: tuple[int,int,int,int] | None` (x, y, w, h).

### OCR engine extension

- **`ievr_bot/ocr.py`** — add `read_boxes(frame) -> list[TextBox]` to the
  `OcrEngine` protocol, where `TextBox` carries `box` (4 points or x/y/w/h),
  `text`, `score`. RapidOCR already returns `[box, text, score]`; we currently
  discard the box in `read()`.
  - `RapidOcrEngine.read_boxes` returns the structured lines.
  - `read()` is reimplemented on top of `read_boxes()` (returns just the texts)
    so existing callers/tests are unaffected.
  - Test fakes implement `read_boxes`; a default `read` can be provided.

### GUI

- **`gui/app.py`** — wrap the current central widget in a `QTabWidget`:
  - **"Run"** tab: the existing controls/panels, unchanged behaviour.
  - **"Templates"** tab: the new flow.
- **`gui/record_worker.py` — `RecordWorker(QThread)`**
  Mirrors `BotWorker`: builds the frame source from the profile, runs
  `MatchRecorder.record`, emits a live preview frame + frame count, and emits the
  recorded frames on finish. Stop via a `threading.Event`.
- **`gui/template_tab.py` — `TemplateTab(QWidget)`**
  - Profile selector + **Record/Stop** buttons, live preview (reuse
    `PreviewPanel`) and a frame counter.
  - On stop: runs `extract_candidates` (off the UI thread if slow) and shows a
    review grid — one row per `GameState`:
    - the current candidate frame with the proposed crop rectangle overlaid as a
      draggable/resizable box,
    - `< >` to cycle candidates, a "skip" toggle,
    - states with no candidate show "no candidate — skip or capture manually".
  - **Save** writes each non-skipped state's cropped region to
    `templates/<profile>/<state>.png` (BGR; `vision.py` reads it grayscale).
    Creates the directory if needed; overwrites existing templates.

## Data flow

```
Record (RecordWorker → MatchRecorder, in-memory frames)
  → extract_candidates (detector + OCR boxes)
  → {state: [Candidate...]}
  → review grid (pick candidate, refine crop, skip)
  → write cropped PNGs to templates/<profile>/
```

No video file is persisted; only the chosen templates are written.

## Error handling / edge cases

- States not seen during the match → row marked "no candidate".
- `WindowCapture` errors (window gone, all-black frame) are logged and the
  offending grab is skipped; recording continues.
- Recording runs on its own `QThread`; the GUI stays responsive; Stop sets the
  event (5s join like `BotWorker`).
- Frame cap reached → recording stops, status notes it.
- Saving with every state skipped → no-op with a status message.

## Testing (TDD)

- `recorder`: fake source returns canned frames; assert N frames recorded,
  stop-event honoured, frame cap honoured, grab exceptions skipped not fatal.
- `template_extractor`: synthetic frames + fake detector/OCR; assert grouping by
  state, top-N ordering by score, crop box = padded union of matching text
  boxes, `None` crop when no box matches, `UNKNOWN` excluded.
- `ocr.read_boxes`: fake/structured engine returns boxes; `read()` still returns
  the list of strings (back-compat).
- GUI glue stays thin; core logic (recorder, extractor) is Qt-free and covered
  by the above.

## Out of scope

- Persisting a video file (frames stay in memory).
- Removing `tools/capture_templates.py` (kept as a CLI fallback).
- Any change to OCR detection behaviour or profiles' `detection` setting.
