"""The semantic algorithm: raw extracted colors -> a role palette.

Hue roles are anchored to canonical angles with saturation borrowed from the
wallpaper's "mood" (average saturation). `accent` is the most-saturated raw
color (the wallpaper's signature). `bg` is pinned near-black, tinted by the
dominant hue.
"""
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


def mood_saturation(raw: list[str]) -> float:
    sats = [color.hsl(c)[1] for c in raw]
    return sum(sats) / len(sats)


def build_palette(raw: list[str], manifest) -> dict:
    hues = {**DEFAULT_HUES, **manifest.hues}
    strength = manifest.mood.get("saturation_strength", 1.0)
    bg_l = manifest.mood.get("bg_lightness", 0.07)

    sat = min(1.0, mood_saturation(raw) * strength)
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


def compile_theme(root, name, manifest) -> dict:
    tp = catalog.theme_paths(root, name)
    raw = extract_mod.extract(manifest.extract_command, tp.wallpaper)
    pal = build_palette(raw, manifest)
    palette_mod.dump(pal, tp.palette)
    return pal
