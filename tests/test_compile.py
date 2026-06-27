import subprocess
import types

import pytest

from adorn import catalog, color, compile as compile_mod
from adorn.manifest import DEFAULT_EXTRACT


def fake_scheme(**over):
    cfg = {
        "mood": {"saturation_strength": 1.0, "bg_lightness": 0.07},
        "list": {"name": "grad", "length": 7, "hues": [300, 215, 175, 120, 40]},
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


def test_single_list_still_works():
    p = compile_mod.build_palette(RAW, fake_scheme(list={"name": "grad", "length": 7, "hues": [300, 120, 40]}))
    assert isinstance(p["grad"], list) and len(p["grad"]) == 7


def test_multiple_lists():
    cfg = fake_scheme(list=[
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
    subprocess.run(["magick", "-size", "16x16", "xc:#9b9e61", str(img)], check=True)
    (tmp_path / "schemes" / "default").mkdir(parents=True)
    (tmp_path / "schemes" / "default" / "scheme.toml").write_text(
        '[mood]\nbg_lightness=0.07\n[list]\nname="grad"\nlength=7\nhues=[300,215,175,120,40]\n',
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


def test_merge_empty_override_returns_base():
    base = {"mood": {"bg_lightness": 0.07, "saturation_strength": 1.0}, "hues": {"red": 0}}
    assert compile_mod.merge_scheme_config(base, {}) == base


def test_merge_mood_is_per_key():
    base = {"mood": {"bg_lightness": 0.07, "saturation_strength": 1.0}}
    merged = compile_mod.merge_scheme_config(base, {"mood": {"bg_lightness": 0.03}})
    assert merged["mood"] == {"bg_lightness": 0.03, "saturation_strength": 1.0}


def test_merge_hues_is_per_key():
    base = {"hues": {"red": 0, "blue": 215}}
    merged = compile_mod.merge_scheme_config(base, {"hues": {"red": 10}})
    assert merged["hues"] == {"red": 10, "blue": 215}


def test_merge_fixed_is_per_key():
    base = {"fixed": {"bg": "#000000", "accent": "#111111"}}
    merged = compile_mod.merge_scheme_config(base, {"fixed": {"accent": "#abcdef"}})
    assert merged["fixed"] == {"bg": "#000000", "accent": "#abcdef"}


def test_merge_lists_by_name_replace_and_append():
    base = {"list": [
        {"name": "grad", "length": 7, "hues": [300, 120]},
        {"name": "warm", "length": 3, "hues": [10, 40]},
    ]}
    override = {"list": [
        {"name": "grad", "length": 5, "hues": [200]},   # replaces same-name
        {"name": "cool", "length": 2, "hues": [200, 240]},  # appends
    ]}
    merged = compile_mod.merge_scheme_config(base, override)
    by_name = {a["name"]: a for a in merged["list"]}
    assert by_name["grad"]["length"] == 5
    assert by_name["warm"]["length"] == 3
    assert by_name["cool"]["length"] == 2


def test_merge_single_list_dict_normalizes():
    base = {"list": {"name": "grad", "length": 7, "hues": [300, 120]}}
    override = {"list": {"name": "grad", "length": 4, "hues": [200]}}
    merged = compile_mod.merge_scheme_config(base, override)
    by_name = {a["name"]: a for a in merged["list"]}
    assert by_name["grad"]["length"] == 4


def test_merge_does_not_mutate_base():
    base = {"mood": {"bg_lightness": 0.07}}
    compile_mod.merge_scheme_config(base, {"mood": {"bg_lightness": 0.03}})
    assert base["mood"]["bg_lightness"] == 0.07


def test_compile_theme_applies_theme_override(tmp_path):
    d = catalog.new_theme_dir(tmp_path, "t")
    img = d / "wallpaper.png"
    # argv list, no shell — matches the no-shell convention in color.py
    subprocess.run(["magick", "-size", "16x16", "xc:#9b9e61", str(img)], check=True)
    (tmp_path / "schemes" / "default").mkdir(parents=True)
    (tmp_path / "schemes" / "default" / "scheme.toml").write_text(
        '[mood]\nbg_lightness=0.07\n[list]\nname="grad"\nlength=7\nhues=[300,215,175,120,40]\n',
        encoding="utf-8",
    )
    # theme pins accent on top of the scheme's wallpaper-derived accent
    (d / "theme.toml").write_text(
        'scheme = "default"\n[fixed]\naccent = "#abcdef"\n', encoding="utf-8"
    )
    m = types.SimpleNamespace(extract_command=DEFAULT_EXTRACT, schemes_dir=tmp_path / "schemes")
    result = compile_mod.compile_theme(tmp_path, "t", m)
    assert result.palette["accent"] == "#abcdef"   # theme override reached derivation
