"""A palette is a flat dict of role -> "#rrggbb", with array roles as lists.

Stored as TOML. Reading uses stdlib tomllib; writing uses a tiny serializer
(values are only strings or lists of strings) to avoid a write-side dependency.
"""
import tomllib
from pathlib import Path


def load(path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return tomllib.loads(p.read_text(encoding="utf-8"))


def merge(base: dict, override: dict) -> dict:
    """Layer override on top of base; override keys win."""
    return {**base, **override}


def dump(palette: dict, path) -> None:
    lines = []
    for key, value in palette.items():
        if isinstance(value, list):
            items = ", ".join(f'"{v}"' for v in value)
            lines.append(f"{key} = [{items}]")
        else:
            lines.append(f'{key} = "{value}"')
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
