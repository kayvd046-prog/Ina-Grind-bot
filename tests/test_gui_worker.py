import pytest

pytest.importorskip("PySide6")


def test_bot_worker_constructs():
    from ievr_bot.config import load_profile
    from pathlib import Path
    from gui.worker import BotWorker
    profiles = Path(__file__).resolve().parents[1] / "profiles"
    profile = load_profile("pve", profiles)
    w = BotWorker(profile, controller_kind="null", dry_run=True)
    assert hasattr(w, "status")
    assert hasattr(w, "log_line")
    assert callable(w.stop)
