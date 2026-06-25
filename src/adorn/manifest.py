"""Load and validate adorn.toml into typed Manifest/Target objects."""
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_EXTRACT = (
    "magick {path} -resize 10% -colors 16 -depth 8 -format %c histogram:info:-"
)


@dataclass(frozen=True)
class Target:
    name: str
    template: str | None = None
    fragment: str | None = None
    reload: str | None = None


@dataclass(frozen=True)
class Manifest:
    root: Path
    templates_dir: Path
    themes_dir: Path
    extract_command: str
    wallpaper_command: str | None
    mood: dict
    ramp: dict | None
    hues: dict
    targets: tuple[Target, ...]


def load(path) -> Manifest:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"no adorn manifest at {path} — run 'adorn init' to create one, or pass --root"
        )
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    root = path.parent

    raw_targets = data.get("target", [])
    if not raw_targets:
        raise ValueError("manifest defines no [[target]] entries")

    targets = []
    for t in raw_targets:
        if "name" not in t:
            raise ValueError(f"target missing name: {t!r}")
        targets.append(
            Target(
                name=t["name"],
                template=t.get("template"),
                fragment=t.get("fragment"),
                reload=t.get("reload"),
            )
        )

    return Manifest(
        root=root,
        templates_dir=root / "templates",
        themes_dir=root / "themes",
        extract_command=data.get("extract", {}).get("command", DEFAULT_EXTRACT),
        wallpaper_command=data.get("wallpaper", {}).get("command"),
        mood=data.get("mood", {}),
        ramp=data.get("ramp"),
        hues=data.get("hues", {}),
        targets=tuple(targets),
    )
