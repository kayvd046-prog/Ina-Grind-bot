"""Build standalone executables and stage editable data next to them.

Run with the project venv:
    .venv\\Scripts\\python build_exe.py

Produces dist/IEVR.exe, dist/capture_templates.exe, and copies the
profiles/ and templates/ folder structure alongside them.
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"


def main() -> None:
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
         str(ROOT / "IEVR.spec")],
        check=True,
    )
    # Ship editable data next to the exes (profiles editable; templates empty
    # folders for the user to capture into). Existing .png templates are not
    # copied — the user captures their own.
    for name in ("profiles", "templates"):
        dst = DIST / name
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(ROOT / name, dst,
                        ignore=shutil.ignore_patterns("*.png"))
    print(f"\nBuild complete. See {DIST}")
    print("  - IEVR.exe              (double-click to run the bot GUI)")
    print("  - capture_templates.exe (run once to capture reference screens)")


if __name__ == "__main__":
    main()
