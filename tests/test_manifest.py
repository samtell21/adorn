from pathlib import Path

import pytest

from adorn import manifest

MANIFEST = """
[mood]
saturation_strength = 1.0
bg_lightness = 0.07

[ramp]
name = "grad"
length = 7
hues = [300, 215, 175, 120, 40]

[wallpaper]
command = "swaymsg output '*' bg {path} fill"

[[target]]
name = "kitty"
template = "kitty.conf.tmpl"
fragment = "colors.conf"
reload = "kitty @ set-colors --all ~/.config/kitty/colors.conf"
"""


def _write(tmp_path, text):
    p = tmp_path / "adorn.toml"
    p.write_text(text)
    return p


def test_load_parses_targets_and_sections(tmp_path):
    m = manifest.load(_write(tmp_path, MANIFEST))
    assert m.root == tmp_path
    assert m.schemes_dir == tmp_path / "schemes"
    assert m.themes_dir == tmp_path / "themes"
    assert len(m.targets) == 1
    t = m.targets[0]
    assert t.name == "kitty"
    assert t.template == "kitty.conf.tmpl"
    assert t.reload.startswith("kitty @ set-colors")
    assert t.fragment == "colors.conf"


def test_extract_defaults_when_absent(tmp_path):
    m = manifest.load(_write(tmp_path, MANIFEST))
    assert m.extract_command == manifest.DEFAULT_EXTRACT
    assert "magick" in m.extract_command


def test_custom_extract_command(tmp_path):
    text = MANIFEST + '\n[extract]\ncommand = "wallust export {path}"\n'
    m = manifest.load(_write(tmp_path, text))
    assert m.extract_command == "wallust export {path}"


def test_no_targets_raises(tmp_path):
    with pytest.raises(ValueError, match="no .*target"):
        manifest.load(_write(tmp_path, "[mood]\nbg_lightness = 0.07\n"))


def test_target_fields(tmp_path):
    text = '[[target]]\nname = "x"\ntemplate = "x.tmpl"\nfragment = "c"\nreload = "true"\n'
    m = manifest.load(_write(tmp_path, text))
    t = m.targets[0]
    assert (t.name, t.template, t.fragment, t.reload) == ("x", "x.tmpl", "c", "true")
    assert not hasattr(t, "via")
