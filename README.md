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
5. Capture reference screenshots:
   `.venv\Scripts\python tools\capture_templates.py --profile pve`
   Then crop each saved PNG in `templates/pve/` down to the distinctive UI
   element for that screen (button, banner, dialog).

## Standalone exe (no Python needed)

Build once, then just double-click:

```
.venv\Scripts\python build_exe.py
```

This produces in `dist/`:
- **`IEVR.exe`** — the bot GUI; double-click to run.
- **`capture_templates.exe`** — run once during setup to capture reference
  screens.
- `profiles/` and `templates/` folders next to the exes — edit profiles and
  capture templates here (the exe reads these from its own folder).

Distribute the whole `dist/` folder together. Still install the **ViGEmBus**
driver on any machine that will send controller input.

## Run (from source)

GUI: `.venv\Scripts\python run_gui.py`
Headless: `.venv\Scripts\python main.py --profile pve` (add `--dry-run` to
observe without sending input, `--controller keyboard` for the keyboard
fallback).

Start the game and leave it at the main menu, then press **Start** in the GUI.

## Tests

`.venv\Scripts\python -m pytest -v`

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
