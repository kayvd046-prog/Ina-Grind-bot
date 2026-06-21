from dataclasses import dataclass
from pathlib import Path
import yaml

REQUIRED_BUTTONS = ("confirm", "cancel", "commander_toggle", "menu")
DEFAULT_PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


@dataclass
class Profile:
    name: str
    mode: str
    templates_dir: Path
    button_map: dict
    timings: dict
    match_threshold: float = 0.85
    phase2_enabled: bool = False


def load_profile(name: str, profiles_dir: Path | None = None) -> Profile:
    base = profiles_dir or DEFAULT_PROFILES_DIR
    path = base / f"{name}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {path}")
    data = yaml.safe_load(path.read_text())
    button_map = data.get("button_map", {})
    missing = [b for b in REQUIRED_BUTTONS if b not in button_map]
    if missing:
        raise ValueError(f"Profile '{name}' missing buttons: {missing}")
    templates_root = base.parent / "templates"
    return Profile(
        name=data["name"],
        mode=data["mode"],
        templates_dir=templates_root / data["templates_subdir"],
        button_map=button_map,
        timings=data.get("timings", {}),
        match_threshold=float(data.get("match_threshold", 0.85)),
        phase2_enabled=bool(data.get("phase2_enabled", False)),
    )
