"""Build the single self-contained executable.

Run with the project venv:
    .venv\\Scripts\\python build_exe.py

Produces dist/IEVR.exe and nothing else: profiles and the OCR models are
bundled inside the exe; captured templates and logs are written at runtime
under %LOCALAPPDATA%\\IEVR.
"""
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
    print(f"\nBuild complete. See {DIST}")
    print("  - IEVR.exe  (single file — double-click to run the bot + setup)")
    print("    Setup lives in the GUI's Templates tab; captured templates and")
    print("    logs are written under %LOCALAPPDATA%\\IEVR.")


if __name__ == "__main__":
    main()
