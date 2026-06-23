"""Interactive helper to capture reference screenshots for state detection.

Usage: python tools/capture_templates.py --profile pve
For each state, position the game on that screen, then press ENTER to save.
Press 's' then ENTER to skip a state, 'q' then ENTER to quit.
"""
import argparse
import cv2
from ievr_bot.capture import ScreenCapture
from ievr_bot.states import GameState
from ievr_bot.paths import templates_root

CAPTURE_STATES = [
    GameState.MAIN_MENU, GameState.LOADING, GameState.KICKOFF,
    GameState.IN_MATCH, GameState.HALFTIME, GameState.GOAL,
    GameState.FULLTIME, GameState.REWARDS, GameState.POST_MATCH,
    GameState.REMATCH, GameState.ERROR_DIALOG,
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="pve")
    args = ap.parse_args()
    out = templates_root() / args.profile
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
