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


# RAW is a muted set: avg saturation is low, so floor 0 stays muted.
RAW = ["#2d2d30", "#9b9e61", "#403f3c", "#595b57"]


def test_floor_zero_is_pure_mood():
    p = compile_mod.build_palette(RAW, fake_manifest(), saturation_floor=0.0)
    assert color.hsl(p["red"])[1] < 0.25  # stays muted at floor 0


def test_floor_lifts_hue_saturation():
    p = compile_mod.build_palette(RAW, fake_manifest(), saturation_floor=0.5)
    for role in ("red", "green", "blue", "yellow", "cyan", "magenta"):
        assert color.hsl(p[role])[1] >= 0.45, f"{role} not lifted to floor"


def test_floor_lifts_ramp_too():
    p = compile_mod.build_palette(RAW, fake_manifest(), saturation_floor=0.5)
    # gradient interpolates in RGB space so intermediate colors may be slightly
    # below the floor; check that they are clearly lifted above floor=0 baseline
    assert all(color.hsl(c)[1] >= 0.40 for c in p["grad"])


def test_floor_does_not_touch_accent():
    # accent is the most-saturated raw color, passed through unchanged
    p = compile_mod.build_palette(RAW, fake_manifest(), saturation_floor=0.5)
    assert p["accent"] == "#9b9e61"


def test_manifest_floor_used_when_no_override():
    m = fake_manifest(mood={"saturation_strength": 1.0, "bg_lightness": 0.07,
                            "hue_saturation_floor": 0.4})
    p = compile_mod.build_palette(RAW, m)  # no explicit override
    assert color.hsl(p["red"])[1] >= 0.35


def test_explicit_override_beats_manifest():
    m = fake_manifest(mood={"saturation_strength": 1.0, "bg_lightness": 0.07,
                            "hue_saturation_floor": 0.2})
    p = compile_mod.build_palette(RAW, m, saturation_floor=0.6)
    assert color.hsl(p["red"])[1] >= 0.55


def test_compile_theme_returns_result_with_stats(tmp_path):
    d = catalog.new_theme_dir(tmp_path, "t")
    img = d / "wallpaper.png"
    subprocess.run(f"magick -size 16x16 xc:#9b9e61 {img}", shell=True, check=True)
    result = compile_mod.compile_theme(tmp_path, "t", fake_manifest(), saturation_floor=0.5)
    assert (d / "palette.toml").exists()
    assert "accent" in result.palette
    assert result.saturation_floor == 0.5
    assert result.effective_saturation >= 0.5
    assert len(result.raw) >= 1
    assert 0.0 <= result.mood_saturation <= 1.0


def test_format_stats_contains_key_fields():
    result = compile_mod.CompileResult(
        palette={"accent": "#9b9e61", "bg": "#131311", "fg": "#d4d5cd",
                 "red": "#cc6666", "yellow": "#ccbb66", "green": "#66cc66",
                 "blue": "#6691cc", "cyan": "#66ccc3", "magenta": "#cc66cc"},
        raw=["#9b9e61", "#2d2d30"], mood_saturation=0.11, saturation_floor=0.30,
        strength=1.0, effective_saturation=0.30, wallpaper="/x/wall.png",
    )
    s = compile_mod.format_stats("succ", result)
    assert "succ" in s
    assert "/x/wall.png" in s
    assert "mood sat" in s and "0.11" in s
    assert "sat floor" in s and "0.30" in s
    assert "hue sat" in s
    assert "#9b9e61" in s  # accent shown
    assert "red" in s and "#cc6666" in s


def test_build_palette_rejects_floor_above_one():
    with pytest.raises(ValueError, match=r"\[0.0, 1.0\]"):
        compile_mod.build_palette(RAW, fake_manifest(), saturation_floor=1.5)


def test_build_palette_rejects_negative_floor():
    with pytest.raises(ValueError, match=r"\[0.0, 1.0\]"):
        compile_mod.build_palette(RAW, fake_manifest(), saturation_floor=-0.1)


def test_accent_too_dark_is_lifted_into_visible_band():
    raw = ["#0a2a1a", "#202020", "#181818"]  # most-saturated is the dark green-teal
    p = compile_mod.build_palette(raw, fake_manifest())
    h, s, l = color.hsl(p["accent"])
    assert l >= 0.40, f"accent lightness {l} not lifted"
    assert 120 <= h <= 175, f"accent hue {h} not preserved (~green-teal)"


def test_accent_in_band_is_unchanged():
    # RAW's most-saturated (#9b9e61) has L~0.50, already in band -> untouched
    p = compile_mod.build_palette(RAW, fake_manifest())
    assert p["accent"] == "#9b9e61"
