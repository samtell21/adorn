import subprocess
import types

import pytest

from adorn import catalog, color, compile as compile_mod
from adorn.manifest import DEFAULT_EXTRACT


def fake_manifest(**over):
    base = dict(
        root=None, templates_dir=None, themes_dir=None,
        extract_command=DEFAULT_EXTRACT, wallpaper_command=None,
        mood={"saturation_strength": 1.0, "bg_lightness": 0.07},
        ramp={"name": "grad", "length": 7, "hues": [300, 215, 175, 120, 40]},
        hues={}, targets=(),
    )
    base.update(over)
    return types.SimpleNamespace(**base)


def approx(a, b, tol):
    return abs(a - b) <= tol


RAW = ["#2d2d30", "#9b9e61", "#403f3c", "#595b57"]  # green is most saturated


def test_accent_is_most_saturated_raw():
    p = compile_mod.build_palette(RAW, fake_manifest())
    assert p["accent"] == "#9b9e61"


def test_background_is_very_dark():
    p = compile_mod.build_palette(RAW, fake_manifest())
    assert color.hsl(p["bg"])[2] < 0.15


def test_hue_roles_anchored():
    p = compile_mod.build_palette(RAW, fake_manifest())
    red_h = color.hsl(p["red"])[0]
    assert red_h < 10 or red_h > 350
    assert approx(color.hsl(p["green"])[0], 120, 8)
    assert approx(color.hsl(p["blue"])[0], 215, 8)


def test_semantic_aliases_and_ramp():
    p = compile_mod.build_palette(RAW, fake_manifest())
    assert p["urgent"] == p["red"]
    assert p["success"] == p["green"]
    assert p["warning"] == p["yellow"]
    assert isinstance(p["grad"], list) and len(p["grad"]) == 7


def test_custom_hue_override():
    p = compile_mod.build_palette(RAW, fake_manifest(hues={"red": 10}))
    assert approx(color.hsl(p["red"])[0], 10, 8)


def test_compile_theme_writes_palette(tmp_path):
    # build a minimal catalog with a real solid wallpaper
    d = catalog.new_theme_dir(tmp_path, "t")
    img = d / "wallpaper.png"
    subprocess.run(f"magick -size 16x16 xc:#9b9e61 {img}", shell=True, check=True)
    m = fake_manifest()
    result = compile_mod.compile_theme(tmp_path, "t", m)
    assert (d / "palette.toml").exists()
    assert "accent" in result.palette and "bg" in result.palette and "grad" in result.palette


def test_mood_saturation_empty_returns_zero():
    assert compile_mod.mood_saturation([]) == 0.0


def test_build_palette_empty_raises():
    with pytest.raises(ValueError, match="at least one raw color"):
        compile_mod.build_palette([], fake_manifest())


def test_all_six_hue_roles_anchored():
    p = compile_mod.build_palette(RAW, fake_manifest())
    for role, expected_h in compile_mod.DEFAULT_HUES.items():
        h = color.hsl(p[role])[0]
        # red sits near 0/360; allow wrap-around
        if expected_h == 0:
            assert h < 10 or h > 350, f"{role} hue {h} not near 0/360"
        else:
            assert approx(h, expected_h, 8), f"{role} hue {h} not near {expected_h}"
