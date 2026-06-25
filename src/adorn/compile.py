"""The semantic algorithm: raw extracted colors -> a role palette.

Hue roles are anchored to canonical angles with saturation borrowed from the
wallpaper's "mood" (average saturation). `accent` is the most-saturated raw
color (the wallpaper's signature). `bg` is pinned near-black, tinted by the
dominant hue.
"""
from dataclasses import dataclass

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


def build_palette(raw: list[str], manifest, *, saturation_floor=None) -> dict:
    if not raw:
        raise ValueError("build_palette requires at least one raw color")
    hues = {**DEFAULT_HUES, **manifest.hues}
    strength = manifest.mood.get("saturation_strength", 1.0)
    bg_l = manifest.mood.get("bg_lightness", 0.07)
    if saturation_floor is None:
        saturation_floor = manifest.mood.get("hue_saturation_floor", 0.0)

    sat = max(saturation_floor, min(1.0, mood_saturation(raw) * strength))
    # most-saturated raw color is the wallpaper's signature; max() picks the
    # first on ties (rare, any winner is acceptable)
    accent = max(raw, key=lambda c: color.hsl(c)[1])
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

    ramp = manifest.ramp
    if ramp:
        stops = [color.make_hsl(h, sat, HUE_LIGHTNESS) for h in ramp["hues"]]
        pal[ramp["name"]] = color.gradient(stops, ramp["length"])

    return pal


def compile_theme(root, name, manifest, *, saturation_floor=None) -> CompileResult:
    tp = catalog.theme_paths(root, name)
    raw = extract_mod.extract(manifest.extract_command, tp.wallpaper)
    strength = manifest.mood.get("saturation_strength", 1.0)
    if saturation_floor is None:
        saturation_floor = manifest.mood.get("hue_saturation_floor", 0.0)
    mood_sat = mood_saturation(raw)
    effective = max(saturation_floor, min(1.0, mood_sat * strength))
    pal = build_palette(raw, manifest, saturation_floor=saturation_floor)
    palette_mod.dump(pal, tp.palette)
    return CompileResult(
        palette=pal, raw=raw, mood_saturation=mood_sat,
        saturation_floor=saturation_floor, strength=strength,
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
        f"  sat floor   {result.saturation_floor:.2f}   (--saturation)",
        f"  hue sat     {result.effective_saturation:.2f}   (effective = clamp(mood*strength, floor, 1.0))",
        f"  accent      {p['accent']}   {hsl_str(p['accent'])}   (image-derived)",
        f"  bg {p['bg']}   fg {p['fg']}",
        f"  red {p['red']}  yellow {p['yellow']}  green {p['green']}",
        f"  blue {p['blue']}  cyan {p['cyan']}  magenta {p['magenta']}",
    ])
