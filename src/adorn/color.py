"""Thin wrappers around the `pastel` CLI for color math.

All calls use argv lists with NO shell, so color values (which can originate
from a hand-edited overrides.toml via Jinja filters) cannot inject commands.
"""
import re
import subprocess

_HSL_RE = re.compile(r"hsl\(\s*([\d.]+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%\s*\)")


def _run(args, stdin=None):
    return subprocess.run(args, input=stdin, capture_output=True, text=True, check=True).stdout


def _to_hex(stdin):
    return _run(["pastel", "format", "hex"], stdin=stdin).strip().lower()


def hsl(c: str) -> tuple[float, float, float]:
    """Return (hue 0-360, saturation 0-1, lightness 0-1)."""
    out = _run(["pastel", "format", "hsl", c])
    m = _HSL_RE.search(out)
    if not m:
        raise ValueError(f"could not parse pastel hsl output: {out!r}")
    return float(m.group(1)), float(m.group(2)) / 100, float(m.group(3)) / 100


def make_hsl(h: float, s: float, l: float) -> str:
    """Build a #rrggbb color from HSL (h degrees, s/l in 0-1)."""
    spec = f"hsl({h:.0f}, {s * 100:.1f}%, {l * 100:.1f}%)"
    return _to_hex(_run(["pastel", "color", spec]))


def lighten(c: str, amount: float) -> str:
    return _to_hex(_run(["pastel", "lighten", str(amount), c]))


def darken(c: str, amount: float) -> str:
    return _to_hex(_run(["pastel", "darken", str(amount), c]))


def mix(c1: str, c2: str, fraction: float = 0.5) -> str:
    # c1 mixed toward c2 by `fraction` (verified: pastel color C1 | pastel mix --fraction F C2)
    step = _run(["pastel", "color", c1])
    return _to_hex(_run(["pastel", "mix", "--fraction", str(fraction), c2], stdin=step))


def gradient(stops: list[str], n: int) -> list[str]:
    """Return n #rrggbb colors interpolated across the given stops."""
    grad = _run(["pastel", "gradient", "-n", str(n), *stops])
    out = _run(["pastel", "format", "hex"], stdin=grad)
    return [ln.strip().lower() for ln in out.splitlines() if ln.strip()]


def rgb_triple(c: str) -> str:
    """Convert #rrggbb to an ANSI 24-bit 'r;g;b' triple (e.g. '#9fb06a' -> '159;176;106')."""
    return f"{int(c[1:3], 16)};{int(c[3:5], 16)};{int(c[5:7], 16)}"
