"""Theme catalog: theme directories and the `current` symlink."""
import os
import tomllib
from collections import namedtuple
from pathlib import Path

ThemePaths = namedtuple("ThemePaths", "dir wallpaper palette overrides meta")


def themes_dir(root) -> Path:
    return Path(root) / "themes"


def current_link(root) -> Path:
    return Path(root) / "current"


def list_themes(root) -> list[str]:
    d = themes_dir(root)
    if not d.is_dir():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_dir())


def current_theme(root) -> str | None:
    link = current_link(root)
    if link.is_symlink() and link.exists():
        return Path(os.readlink(link)).name
    return None


def set_current(root, name) -> None:
    link = current_link(root)
    target = themes_dir(root) / name
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(target)


def theme_paths(root, name) -> ThemePaths:
    d = themes_dir(root) / name
    wallpaper = next(iter(sorted(d.glob("wallpaper.*"))), d / "wallpaper")
    return ThemePaths(
        dir=d,
        wallpaper=wallpaper,
        palette=d / "palette.toml",
        overrides=d / "overrides.toml",
        meta=d / "theme.toml",
    )


def new_theme_dir(root, name) -> Path:
    d = themes_dir(root) / name
    d.mkdir(parents=True, exist_ok=False)
    return d


def theme_scheme(theme_paths) -> str:
    meta = theme_paths.meta
    if meta.exists():
        return tomllib.loads(meta.read_text(encoding="utf-8")).get("scheme", "default")
    return "default"


def theme_overrides(theme_paths) -> dict:
    """The theme's derivation overrides: theme.toml minus the `scheme` key."""
    meta = theme_paths.meta
    if not meta.exists():
        return {}
    data = tomllib.loads(meta.read_text(encoding="utf-8"))
    data.pop("scheme", None)
    return data
