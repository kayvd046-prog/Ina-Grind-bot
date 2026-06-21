import pytest
from pathlib import Path
from ievr_bot.config import load_profile, Profile, REQUIRED_BUTTONS


PROFILES = Path(__file__).resolve().parents[1] / "profiles"


def test_load_pve_profile():
    p = load_profile("pve", PROFILES)
    assert isinstance(p, Profile)
    assert p.mode == "pve"
    assert p.match_threshold == 0.85
    assert p.timings["poll_interval"] == 0.4
    assert p.capture_backend == "window"
    assert p.window_title  # non-empty
    for b in REQUIRED_BUTTONS:
        assert b in p.button_map


def test_unknown_profile_raises():
    with pytest.raises(FileNotFoundError):
        load_profile("does_not_exist", PROFILES)


def test_missing_button_raises(tmp_path):
    (tmp_path / "bad.yaml").write_text(
        "name: bad\nmode: pve\ntemplates_subdir: pve\n"
        "match_threshold: 0.85\nphase2_enabled: false\n"
        "button_map: {confirm: A}\ntimings: {}\n"
    )
    with pytest.raises(ValueError):
        load_profile("bad", tmp_path)
