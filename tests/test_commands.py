# tests/test_commands.py
import subprocess

from adorn import catalog, cli, commands, palette


def build_catalog(root):
    (root / "templates").mkdir(parents=True)
    (root / "templates" / "kitty.conf.tmpl").write_text(
        "background {{ bg }}\naccent {{ accent }}\n"
    )
    marker = root / "reloaded"
    (root / "adorn.toml").write_text(
        f"""
[mood]
bg_lightness = 0.07

[ramp]
name = "grad"
length = 7
hues = [300, 215, 175, 120, 40]

[wallpaper]
command = "true {{path}}"

[[target]]
name = "kitty"
template = "kitty.conf.tmpl"
output = "{root / 'kitty-colors.conf'}"
reload = "touch {marker}"
"""
    )
    return marker


def make_wallpaper(path):
    subprocess.run(f"magick -size 16x16 xc:#9b9e61 {path}", shell=True, check=True)


def test_new_compiles_and_applies(tmp_path):
    marker = build_catalog(tmp_path)
    wp = tmp_path / "src.png"
    make_wallpaper(wp)
    commands.cmd_new(tmp_path, "test", str(wp))

    tp = catalog.theme_paths(tmp_path, "test")
    assert tp.palette.exists()
    assert tp.overrides.exists()
    out = (tmp_path / "kitty-colors.conf").read_text()
    assert out.startswith("background #")
    assert catalog.current_theme(tmp_path) == "test"
    assert marker.exists()


def test_overrides_win_on_apply(tmp_path):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"
    make_wallpaper(wp)
    commands.cmd_new(tmp_path, "test", str(wp), do_apply=True)
    # pin bg via overrides, re-apply
    tp = catalog.theme_paths(tmp_path, "test")
    palette.dump({"bg": "#000000"}, tp.overrides)
    commands.cmd_apply(tmp_path, "test")
    assert "background #000000" in (tmp_path / "kitty-colors.conf").read_text()


def test_effective_palette_merges(tmp_path):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"
    make_wallpaper(wp)
    commands.cmd_new(tmp_path, "test", str(wp), do_apply=False)
    tp = catalog.theme_paths(tmp_path, "test")
    palette.dump({"bg": "#000000"}, tp.overrides)
    eff = commands.effective_palette(tmp_path, "test")
    assert eff["bg"] == "#000000"
    assert "accent" in eff


def test_cli_list_and_current(tmp_path, capsys):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"
    make_wallpaper(wp)
    cli.main(["--root", str(tmp_path), "new", "test", str(wp), "--no-apply"])
    cli.main(["--root", str(tmp_path), "apply", "test"])
    capsys.readouterr()
    cli.main(["--root", str(tmp_path), "list"])
    assert "* test" in capsys.readouterr().out
    cli.main(["--root", str(tmp_path), "current"])
    assert "test" in capsys.readouterr().out
