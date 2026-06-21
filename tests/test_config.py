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


def test_profile_has_detection_and_ocr_defaults(tmp_path):
    (tmp_path / "min.yaml").write_text(
        "name: min\nmode: pve\ntemplates_subdir: pve\n"
        "button_map: {confirm: A, cancel: B, commander_toggle: Y, menu: START}\n"
        "timings: {}\n"
    )
    p = load_profile("min", tmp_path)
    assert p.detection == "composite"   # default when absent
    assert p.ocr == {}                  # default when absent


def test_profile_reads_detection_and_ocr(tmp_path):
    (tmp_path / "ocr.yaml").write_text(
        "name: ocr\nmode: pve\ntemplates_subdir: pve\n"
        "detection: ocr\n"
        "ocr: {lang: en, min_confidence: 0.5, keywords: {GOAL: ['goal']}}\n"
        "button_map: {confirm: A, cancel: B, commander_toggle: Y, menu: START}\n"
        "timings: {}\n"
    )
    p = load_profile("ocr", tmp_path)
    assert p.detection == "ocr"
    assert p.ocr["min_confidence"] == 0.5
    assert p.ocr["keywords"]["GOAL"] == ["goal"]
