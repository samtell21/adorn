"""Run the manifest's extract command and parse #rrggbb colors from stdout."""
import re
import shlex
import subprocess

_HEX_RE = re.compile(r"#([0-9a-fA-F]{6})(?:[0-9a-fA-F]{2})?")


def extract(command: str, wallpaper) -> list[str]:
    cmd = command.format(path=shlex.quote(str(wallpaper)))
    out = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, check=True
    ).stdout
    colors = ["#" + m.group(1).lower() for m in _HEX_RE.finditer(out)]
    if not colors:
        raise ValueError(f"extract command produced no colors: {cmd!r}")
    return colors
