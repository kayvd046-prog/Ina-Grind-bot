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

## Run

GUI: `.venv\Scripts\python run_gui.py`
Headless: `.venv\Scripts\python main.py --profile pve` (add `--dry-run` to
observe without sending input, `--controller keyboard` for the keyboard
fallback).

Start the game and leave it at the main menu, then press **Start** in the GUI.

## Tests

`.venv\Scripts\python -m pytest -v`

## Notes

- Start with **PvE**. Automating online Ranked may violate the game's ToS.
- Tune `match_threshold` and `timings` in `profiles/*.yaml` if detection is
  flaky.
- Detection is resolution-sensitive: recapture templates if you change the game
  resolution or window size.
