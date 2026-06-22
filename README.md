# IEVR Commander-Mode Bot

Autonomous bot that grinds *Inazuma Eleven: Victory Road* matches using the
game's built-in **Commander Mode**. The game's AI plays; the bot detects screens
and presses buttons to loop matches forever. See the design spec in
`docs/superpowers/specs/`.

## One-time setup

1. Install Python 3.11+ (this project was built/tested on 3.14).
2. Create a venv and install deps:
   ```
   py -3.14 -m venv .venv
   .venv\Scripts\python -m pip install -r requirements.txt
   ```
3. Install the **ViGEmBus** driver (required by `vgamepad`):
   https://github.com/ViGEm/ViGEmBus/releases
4. Launch the game, set a **fixed resolution / borderless window**.
5. (Optional — templates are only an OCR fallback.) Capture reference
   screenshots the easy way: open the GUI, go to the **Templates** tab, press
   **Record**, play one full match in Commander Mode, then press **Stop**. The
   bot records itself via the game window (no command prompt over the screen),
   auto-labels the frames with its own detector, and shows a per-state review
   grid with a suggested crop you can drag/resize before **Save**. See
   "Recording templates" below.
   The old interactive CLI still works as a fallback:
   `.venv\Scripts\python tools\capture_templates.py --profile pve` (then crop
   each saved PNG in `templates/pve/` down to the distinctive UI element).

## Standalone exe (no Python needed)

Build once, then just double-click:

```
.venv\Scripts\python build_exe.py
```

This produces a **single self-contained `dist/IEVR.exe`** — nothing beside it:
- The setup is built into the GUI (the **Templates** tab), so there is no
  separate capture tool.
- The default **profiles** and the **OCR models** are bundled *inside* the exe.
- Captured **templates** and **logs** are written at runtime under
  `%LOCALAPPDATA%\IEVR\` (e.g. `C:\Users\<you>\AppData\Local\IEVR`), so the exe
  itself stays a single file you can copy anywhere.

Just ship `IEVR.exe`. Still install the **ViGEmBus** driver on any machine that
will send controller input.

> Note: because profiles are bundled read-only, tuning `timings`/`keywords`
> means editing `profiles/*.yaml` and rebuilding. Run from source (below) if you
> want to tune profiles without rebuilding.

## Run (from source)

GUI: `.venv\Scripts\python run_gui.py`
Headless: `.venv\Scripts\python main.py --profile pve` (add `--dry-run` to
observe without sending input, `--controller keyboard` for the keyboard
fallback).

Start the game and leave it at the main menu, then press **Start** in the GUI.

## Tests

`.venv\Scripts\python -m pytest -v`

## Recording templates (Templates tab)

Instead of stopping at each screen and pressing ENTER in a prompt, let the bot
record a whole match and produce the templates itself:

1. GUI → **Templates** tab → pick the profile → **Record**.
2. Play one full match in Commander Mode. The bot grabs frames from the game
   **window** (same source it plays against), so nothing needs to overlap the
   game and it keeps capturing even while alt-tabbed.
3. **Stop**. The bot runs its own detector over the recording, groups frames by
   game state, and keeps the highest-confidence ones.
4. Review grid: per state you get the best frame with a **suggested crop**
   (drawn around the text that identifies the state). Use *prev/next* to pick a
   different frame, drag the box / its bottom-right handle to adjust the crop,
   or tick **Skip**. States never seen during the match show "no candidate".
5. **Save templates** writes the cropped PNGs to `templates/<profile>/`.

Frames stay in memory; only the templates you keep are written. States OCR
can't label won't get an auto-candidate — capture those with the CLI fallback
if you need them.

## Background / alt-tab operation

The profiles default to `capture_backend: window`, which grabs the game window
directly via the Win32 `PrintWindow` API. This means the bot keeps **seeing** the
game even when it is behind other windows or you have alt-tabbed away (the window
must not be *minimized*). Set `window_title` in `profiles/*.yaml` to a substring
of the game's window title (default: `INAZUMA ELEVEN`). Use
`capture_backend: screen` to capture the visible foreground instead.

Two caveats for true background play:
- **Input:** keyboard input only reaches the focused window, so use the
  **vgamepad** controller (default) — XInput is not focus-bound and many games
  keep reading it in the background.
- **The game must keep running while unfocused.** Some games pause on focus
  loss. Check the game's settings for a "pause when unfocused / run in
  background" option and disable pausing. If the game still pauses, background
  input cannot help — that is a game limitation, not a bot bug.
- Some GPU-accelerated games return black frames with `PrintWindow`; if the
  preview is black while the game is visible, switch to `capture_backend: screen`.

## Notes

- Start with **PvE**. Automating online Ranked may violate the game's ToS.
- The bot detects game screens via **OCR by default** (`detection: composite`
  in each profile). On-screen text is read by RapidOCR and matched against the
  keyword lists in `profiles/*.yaml` → `ocr.keywords`. If a state is missed or
  misidentified, add or adjust keywords there. Note: single-word keywords (e.g.
  "goal") are high-recall but low-precision; matching is whole-word, and
  narrowing `ocr.region` to the banner area improves reliability.
- Reference image templates are an **optional fallback**: the composite
  detector only consults them when OCR confidence is below the threshold. You
  can still capture templates with `capture_templates.exe` for extra robustness,
  but they are not required for basic operation.
- Tune `timings` in `profiles/*.yaml` if button presses arrive too early or
  too late.
- If you switch the game resolution or window size, recapture any template
  images you rely on (OCR is resolution-independent).
