import sys
from pathlib import Path
import ievr_bot.paths as paths

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_from_source_uses_project_root():
    # Not frozen: everything lives in the project root.
    assert paths.profiles_dir() == PROJECT_ROOT / "profiles"
    assert paths.templates_root() == PROJECT_ROOT / "templates"
    assert paths.logs_dir() == PROJECT_ROOT / "logs"


def test_frozen_reads_profiles_from_bundle(monkeypatch, tmp_path):
    bundle = tmp_path / "bundle"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    # profiles are bundled read-only inside the one-file exe
    assert paths.profiles_dir() == bundle / "profiles"


def test_frozen_writes_user_data_under_localappdata(monkeypatch, tmp_path):
    appdata = tmp_path / "AppData"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(appdata))
    # writable data (templates the user captures, logs) lives beside no exe —
    # it goes under %LOCALAPPDATA%\IEVR so the exe stays a single file.
    assert paths.templates_root() == appdata / "IEVR" / "templates"
    assert paths.logs_dir() == appdata / "IEVR" / "logs"
