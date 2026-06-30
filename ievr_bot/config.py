from dataclasses import dataclass, field
from pathlib import Path
import yaml

from .paths import profiles_dir as _default_profiles_dir, templates_root

REQUIRED_BUTTONS = ("confirm", "cancel", "commander_toggle", "menu")


@dataclass
class Profile:
    name: str
    mode: str
    templates_dir: Path
    button_map: dict
    timings: dict
    match_threshold: float = 0.85
    phase2_enabled: bool = False
    capture_backend: str = "screen"  # "screen" or "window"
    window_title: str = ""
    detection: str = "composite"  # "ocr" | "template" | "composite"
    ocr: dict = field(default_factory=dict)


def available_profiles(profiles_dir: Path | None = None) -> list[str]:
    """Return sorted list of profile stems found in profiles_dir."""
    base = profiles_dir or _default_profiles_dir()
    if not base.exists():
        return []
    return sorted(p.stem for p in base.glob("*.yaml"))


def load_profile(name: str, profiles_dir: Path | None = None) -> Profile:
    base = profiles_dir or _default_profiles_dir()
    path = base / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {path}")
    data = yaml.safe_load(path.read_text())
    button_map = data.get("button_map", {})
    missing = [b for b in REQUIRED_BUTTONS if b not in button_map]
    if missing:
        raise ValueError(f"Profile '{name}' missing buttons: {missing}")
    detection = str(data.get("detection", "composite"))
    _VALID_DETECTIONS = {"ocr", "template", "composite"}
    if detection not in _VALID_DETECTIONS:
        raise ValueError(f"Profile '{name}' has invalid detection: {detection!r}")
    # Templates are writable user data, independent of where profiles live
    # (when frozen, profiles are read-only inside the exe but captured
    # templates must persist under the user data dir).
    return Profile(
        name=data["name"],
        mode=data["mode"],
        templates_dir=templates_root() / data["templates_subdir"],
        button_map=button_map,
        timings=data.get("timings", {}),
        match_threshold=float(data.get("match_threshold", 0.85)),
        phase2_enabled=bool(data.get("phase2_enabled", False)),
        capture_backend=str(data.get("capture_backend", "screen")),
        window_title=str(data.get("window_title", "")),
        detection=detection,
        ocr=data.get("ocr", {}) or {},
    )
