import subprocess
import types

import pytest

from adorn import catalog, color, compile as compile_mod
from adorn.manifest import DEFAULT_EXTRACT


def fake_scheme(**over):
    cfg = {
        "mood": {"saturation_strength": 1.0, "bg_lightness": 0.07},
        "ramp": {"name": "grad", "length": 7, "hues": [300, 215, 175, 120, 40]},
        "hues": {},
    }
    cfg.update(over)
    return cfg


def approx(a, b, tol):
    return abs(a - b) <= tol


RAW = ["#2d2d30", "#9b9e61", "#403f3c", "#595b57"]  # green is most saturated


def test_accent_is_most_saturated_raw():
    p = compile_mod.build_palette(RAW, fake_scheme())
    assert p["accent"] == "#9b9e61"


def test_background_is_very_dark():
    p = compile_mod.build_palette(RAW, fake_scheme())
    assert color.hsl(p["bg"])[2] < 0.15


def test_hue_roles_anchored():
    p = compile_mod.build_palette(RAW, fake_scheme())
    red_h = color.hsl(p["red"])[0]
    assert red_h < 10 or red_h > 350
    assert approx(color.hsl(p["green"])[0], 120, 8)
    assert approx(color.hsl(p["blue"])[0], 215, 8)


def test_semantic_aliases_and_ramp():
    p = compile_mod.build_palette(RAW, fake_scheme())
    assert p["urgent"] == p["red"]
    assert p["success"] == p["green"]
    assert p["warning"] == p["yellow"]
    assert isinstance(p["grad"], list) and len(p["grad"]) == 7


def test_single_ramp_still_works():
    p = compile_mod.build_palette(RAW, fake_scheme(ramp={"name": "grad", "length": 7, "hues": [300, 120, 40]}))
    assert isinstance(p["grad"], list) and len(p["grad"]) == 7


def test_multiple_ramps():
    cfg = fake_scheme(ramp=[
        {"name": "grad", "length": 7, "hues": [300, 120, 40]},
        {"name": "warm", "length": 3, "hues": [10, 40]},
    ])
    p = compile_mod.build_palette(RAW, cfg)
    assert len(p["grad"]) == 7 and len(p["warm"]) == 3


def test_custom_hue_override():
    p = compile_mod.build_palette(RAW, fake_scheme(hues={"red": 10}))
    assert approx(color.hsl(p["red"])[0], 10, 8)


def test_compile_theme_writes_palette(tmp_path):
    # build a minimal catalog with a real solid wallpaper
    d = catalog.new_theme_dir(tmp_path, "t")
    img = d / "wallpaper.png"
    subprocess.run(f"magick -size 16x16 xc:#9b9e61 {img}", shell=True, check=True)
    (tmp_path / "schemes" / "default").mkdir(parents=True)
    (tmp_path / "schemes" / "default" / "scheme.toml").write_text(
        '[mood]\nbg_lightness=0.07\n[ramp]\nname="grad"\nlength=7\nhues=[300,215,175,120,40]\n',
        encoding="utf-8",
    )
    (d / "theme.toml").write_text('scheme = "default"\n', encoding="utf-8")
    m = types.SimpleNamespace(extract_command=DEFAULT_EXTRACT, schemes_dir=tmp_path / "schemes")
    result = compile_mod.compile_theme(tmp_path, "t", m)
    assert (d / "palette.toml").exists()
    assert "accent" in result.palette and "bg" in result.palette and "grad" in result.palette


def test_mood_saturation_empty_returns_zero():
    assert compile_mod.mood_saturation([]) == 0.0


def test_build_palette_empty_raises():
    with pytest.raises(ValueError, match="at least one raw color"):
        compile_mod.build_palette([], fake_scheme())


def test_all_six_hue_roles_anchored():
    p = compile_mod.build_palette(RAW, fake_scheme())
    for role, expected_h in compile_mod.DEFAULT_HUES.items():
        h = color.hsl(p[role])[0]
        # red sits near 0/360; allow wrap-around
        if expected_h == 0:
            assert h < 10 or h > 350, f"{role} hue {h} not near 0/360"
        else:
            assert approx(h, expected_h, 8), f"{role} hue {h} not near {expected_h}"


def test_fixed_roles_override_derivation():
    p = compile_mod.build_palette(RAW, fake_scheme(fixed={"bg": "#000000", "accent": "#abcdef"}))
    assert p["bg"] == "#000000"
    assert p["accent"] == "#abcdef"


def test_load_scheme_config(tmp_path):
    sd = tmp_path / "s"
    sd.mkdir()
    (sd / "scheme.toml").write_text(
        '[mood]\nbg_lightness=0.05\n[hues]\nred=10\n', encoding="utf-8"
    )
    cfg = compile_mod.load_scheme_config(sd)
    assert cfg["mood"]["bg_lightness"] == 0.05 and cfg["hues"]["red"] == 10


def test_load_scheme_config_missing_is_empty(tmp_path):
    assert compile_mod.load_scheme_config(tmp_path / "nope") == {}
