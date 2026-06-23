"""Diagnose what the bot sees on the CURRENT game screen.

Navigate the game to the screen you want to inspect (e.g. the rematch prompt),
then run:

    .venv\\Scripts\\python tools\\diagnose_screen.py --profile pve

It grabs one frame from the profile's frame source, saves it as a PNG you can
look at, prints every text line OCR reads (with confidence + box), and prints
which GameState the detector picks. Use this to decide whether a screen is
detectable by OCR (and with which keyword) or needs a template.
"""
import argparse
import sys
import time
from pathlib import Path

# Running a script in tools/ puts tools/ on sys.path, not the project root, so
# `import ievr_bot` fails. Put the project root first.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ievr_bot.config import load_profile
from ievr_bot.paths import profiles_dir
from ievr_bot.capture import build_frame_source
from ievr_bot.diagnostics import diagnose_frame, format_report, save_frame


def _grab(source, tries=5, delay=0.4):
    last = None
    for _ in range(tries):
        try:
            return source.grab()
        except Exception as exc:  # window warmup / transient black frame
            last = exc
            time.sleep(delay)
    raise RuntimeError(f"Could not grab a frame: {last}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="pve")
    args = ap.parse_args()

    profile = load_profile(args.profile, profiles_dir())
    print(f"profile={profile.name}  backend={profile.capture_backend}  "
          f"window_title={profile.window_title!r}  detection={profile.detection}")

    source = build_frame_source(profile)
    frame = _grab(source)

    out_dir = Path(__file__).resolve().parents[1] / "diag"
    png = save_frame(frame, out_dir)
    print(f"\nSaved frame -> {png}\n")

    from ievr_bot.composite_detector import build_detector
    from ievr_bot.ocr import make_ocr_engine
    detector = build_detector(profile)
    engine = make_ocr_engine((profile.ocr or {}).get("lang", "en"))
    print(format_report(diagnose_frame(frame, engine, detector)))

    print("\nConfigured OCR keywords:")
    for name, words in (profile.ocr or {}).get("keywords", {}).items():
        print(f"  {name}: {words}")


if __name__ == "__main__":
    main()
