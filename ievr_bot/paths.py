"""Resolve data directories whether running from source or as a frozen exe.

The packaged build is a single self-contained IEVR.exe with nothing beside it:
- **Bundled, read-only** data (profiles, OCR models) is unpacked by PyInstaller
  into a temp dir exposed as ``sys._MEIPASS``.
- **Writable** data (templates the user captures, logs) cannot live next to a
  one-file exe, so it goes under ``%LOCALAPPDATA%\\IEVR``.

When running from source both live in the project root.
"""
import os
import sys
from pathlib import Path


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def bundle_dir() -> Path:
    """Read-only bundled data. PyInstaller's extraction dir when frozen,
    else the project root."""
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return _project_root()


def user_data_dir() -> Path:
    """Writable per-user data. ``%LOCALAPPDATA%\\IEVR`` when frozen (falling
    back to the home dir), else the project root."""
    if getattr(sys, "frozen", False):
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "IEVR"
    return _project_root()


def app_base_dir() -> Path:
    # Kept for back-compat; bundled (read-only) base.
    return bundle_dir()


def profiles_dir() -> Path:
    return bundle_dir() / "profiles"


def templates_root() -> Path:
    return user_data_dir() / "templates"


def logs_dir() -> Path:
    return user_data_dir() / "logs"
