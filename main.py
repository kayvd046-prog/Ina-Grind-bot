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
