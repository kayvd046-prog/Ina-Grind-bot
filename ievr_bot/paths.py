"""Resolve data directories whether running from source or as a frozen exe.

When frozen by PyInstaller, profiles/, templates/ and logs/ live next to the
executable so the user can capture templates and edit profiles without touching
the bundle. When running from source they live in the project root.
"""
import sys
from pathlib import Path


def app_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def profiles_dir() -> Path:
    return app_base_dir() / "profiles"


def templates_root() -> Path:
    return app_base_dir() / "templates"


def logs_dir() -> Path:
    return app_base_dir() / "logs"
