"""The semantic algorithm: raw extracted colors -> a role palette.

Hue roles are anchored to canonical angles with saturation borrowed from the
wallpaper's "mood" (average saturation). `accent` is the most-saturated raw
color (the wallpaper's signature). `bg` is pinned near-black, tinted by the
dominant hue.
"""
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import catalog, color
from . import extract as extract_mod
from . import palette as palette_mod

DEFAULT_HUES = {
    "red": 0,
    "yellow": 50,
    "green": 120,
    "cyan": 175,
    "blue": 215,
    "magenta": 300,
}
HUE_LIGHTNESS = 0.62  # legibility target for the 6 hue roles on a dark bg
ACCENT_MIN_LIGHTNESS = 0.40
ACCENT_MAX_LIGHTNESS = 0.70


@dataclass
class CompileResult:
    palette: dict
    raw: list[str]
    mood_saturation: float
    saturation_floor: float
    strength: float
    effective_saturation: float
    wallpaper: str


def mood_saturation(raw: list[str]) -> float:
    sats = [color.hsl(c)[1] for c in raw]
    return sum(sats) / len(sats) if sats else 0.0


def load_scheme_config(scheme_dir) -> dict:
    p = Path(scheme_dir) / "scheme.toml"
    if p.exists():
        return tomllib.loads(p.read_text(encoding="utf-8"))
    return {}


def build_palette(raw: list[str], scheme_config: dict, *, saturation_floor=None) -> dict:
    if not raw:
        raise ValueError("build_palette requires at least one raw color")
    mood = scheme_config.get("mood", {})
    hues = {**DEFAULT_HUES, **scheme_config.get("hues", {})}
    fixed = scheme_config.get("fixed", {})
    strength = mood.get("saturation_strength", 1.0)
    bg_l = mood.get("bg_lightness", 0.07)
    if saturation_floor is None:
        saturation_floor = mood.get("hue_saturation_floor", 0.0)
    if not 0.0 <= saturation_floor <= 1.0:
        raise ValueError(f"saturation floor must be in [0.0, 1.0], got {saturation_floor}")

    sat = max(saturation_floor, min(1.0, mood_saturation(raw) * strength))
    # most-saturated raw color is the wallpaper's signature; max() picks the
    # first on ties (rare, any winner is acceptable)
    accent = max(raw, key=lambda c: color.hsl(c)[1])
    # keep the accent's hue+saturation but pull a too-dark/too-light pick into a
    # visible lightness band, so the signature color is always usable
    ah, asat, al = color.hsl(accent)
    if al < ACCENT_MIN_LIGHTNESS:
        accent = color.make_hsl(ah, asat, ACCENT_MIN_LIGHTNESS)
    elif al > ACCENT_MAX_LIGHTNESS:
        accent = color.make_hsl(ah, asat, ACCENT_MAX_LIGHTNESS)
    dom_h = color.hsl(accent)[0]

    pal: dict = {}
    pal["bg"] = color.make_hsl(dom_h, 0.06, bg_l)
    pal["bg_alt"] = color.lighten(pal["bg"], 0.04)
    pal["bg_highlight"] = color.lighten(pal["bg"], 0.10)
    pal["bg_visual"] = color.lighten(pal["bg"], 0.14)
    pal["fg"] = color.make_hsl(dom_h, 0.08, 0.82)
    pal["fg_dim"] = color.make_hsl(dom_h, 0.06, 0.60)
    pal["muted"] = color.make_hsl(dom_h, 0.05, 0.45)
    pal["comment"] = pal["muted"]
    pal["accent"] = accent

    for role, h in hues.items():
        pal[role] = color.make_hsl(h, sat, HUE_LIGHTNESS)
    pal["urgent"] = pal["red"]
    pal["success"] = pal["green"]
    pal["warning"] = pal["yellow"]

    ramps = scheme_config.get("ramp", [])
    if isinstance(ramps, dict):      # backward-compat: a single [ramp] table
        ramps = [ramps]
    for ramp in ramps:
        stops = [color.make_hsl(h, sat, HUE_LIGHTNESS) for h in ramp["hues"]]
        pal[ramp["name"]] = color.gradient(stops, ramp["length"])

    pal.update(fixed)   # scheme's fixed roles win over derivation
    return pal


def compile_theme(root, name, manifest, *, saturation_floor=None) -> CompileResult:
    tp = catalog.theme_paths(root, name)
    scheme_cfg = load_scheme_config(manifest.schemes_dir / catalog.theme_scheme(tp))
    raw = extract_mod.extract(manifest.extract_command, tp.wallpaper)
    mood = scheme_cfg.get("mood", {})
    strength = mood.get("saturation_strength", 1.0)
    floor = saturation_floor if saturation_floor is not None else mood.get("hue_saturation_floor", 0.0)
    mood_sat = mood_saturation(raw)
    effective = max(floor, min(1.0, mood_sat * strength))
    pal = build_palette(raw, scheme_cfg, saturation_floor=saturation_floor)
    palette_mod.dump(pal, tp.palette)
    return CompileResult(
        palette=pal, raw=raw, mood_saturation=mood_sat,
        saturation_floor=floor, strength=strength,
        effective_saturation=effective, wallpaper=str(tp.wallpaper),
    )


def format_stats(name: str, result: CompileResult) -> str:
    def hsl_str(hexv):
        h, s, l = color.hsl(hexv)
        return f"H{h:.0f} S{s * 100:.0f}% L{l * 100:.0f}%"

    p = result.palette
    return "\n".join([
        f"✓ compiled '{name}'",
        f"  wallpaper   {result.wallpaper}",
        f"  raw colors  {len(result.raw)} extracted",
        f"  mood sat    {result.mood_saturation:.2f}   (avg saturation of the wallpaper)",
        f"  sat floor   {result.saturation_floor:.2f}   (--saturation / [mood])",
        f"  hue sat     {result.effective_saturation:.2f}   (effective = clamp(mood*strength, floor, 1.0))",
        f"  accent      {p['accent']}   {hsl_str(p['accent'])}   (image-derived)",
        f"  bg {p['bg']}   fg {p['fg']}",
        f"  red {p['red']}  yellow {p['yellow']}  green {p['green']}",
        f"  blue {p['blue']}  cyan {p['cyan']}  magenta {p['magenta']}",
    ])
