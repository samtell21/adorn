"""Thin wrappers around the `pastel` CLI for color math.

Every transform shells out to pastel and returns a #rrggbb string, keeping
adorn a tiny orchestrator with the color math in one well-tested tool. Inputs
are colors adorn generates, so shell=True is acceptable here.
"""
import re
import subprocess

_HSL_RE = re.compile(r"hsl\(\s*([\d.]+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%\s*\)")


def _run(cmd: str) -> str:
    return subprocess.run(
        cmd, shell=True, capture_output=True, text=True, check=True
    ).stdout.strip()


def _to_hex(pipeline: str) -> str:
    """Run a pastel pipeline yielding one color; return it as #rrggbb."""
    return _run(f"{pipeline} | pastel format hex").strip().lower()


def hsl(c: str) -> tuple[float, float, float]:
    """Return (hue 0-360, saturation 0-1, lightness 0-1)."""
    out = _run(f'pastel format hsl "{c}"')
    m = _HSL_RE.match(out)
    if not m:
        raise ValueError(f"could not parse pastel hsl output: {out!r}")
    return float(m.group(1)), float(m.group(2)) / 100, float(m.group(3)) / 100


def make_hsl(h: float, s: float, l: float) -> str:
    """Build a #rrggbb color from HSL (h degrees, s/l in 0-1)."""
    spec = f"hsl({h:.0f}, {s * 100:.1f}%, {l * 100:.1f}%)"
    return _to_hex(f"pastel color '{spec}'")


def lighten(c: str, amount: float) -> str:
    return _to_hex(f'pastel lighten {amount} "{c}"')


def gradient(stops: list[str], n: int) -> list[str]:
    """Return n #rrggbb colors interpolated across the given stops."""
    quoted_stops = ' '.join(f'"{s}"' for s in stops)
    out = _run(f"pastel gradient -n {n} {quoted_stops} | pastel format hex")
    return [line.strip().lower() for line in out.splitlines() if line.strip()]
