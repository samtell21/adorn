# tests/test_commands.py
import subprocess

from adorn import catalog, cli, commands, palette


def build_catalog(root):
    (root / "templates").mkdir(parents=True)
    (root / "templates" / "waybar.tmpl").write_text("bg {{ bg }}\naccent {{ accent }}\n")
    (root / "templates" / "swaylock.tmpl").write_text("ring={{ accent[1:] }}\n")
    swaycfg = root / "swaylock.conf"
    swaycfg.write_text("font=Foo\nindicator-radius=110\n", encoding="utf-8")
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
name = "waybar"
template = "waybar.tmpl"
fragment = "colors.css"
reload = "true"
[[target]]
name = "swaylock"
template = "swaylock.tmpl"
fragment = "colors"
via = "block"
output = "{swaycfg}"
"""
    )
    return swaycfg


def make_wallpaper(path):
    subprocess.run(f"magick -size 16x16 xc:#9b9e61 {path}", shell=True, check=True)


def test_new_materializes_editable_fragments(tmp_path):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    commands.cmd_new(tmp_path, "t", str(wp))
    tp = catalog.theme_paths(tmp_path, "t")
    waybar_frag = tp.dir / "apps" / "waybar" / "colors.css"
    assert waybar_frag.exists()
    assert waybar_frag.read_text().startswith("bg #")
    # editable + saved: hand-edit survives apply
    waybar_frag.write_text("bg #deadbe\naccent #c0ffee\n", encoding="utf-8")
    commands.cmd_apply(tmp_path, "t")
    assert (tp.dir / "apps" / "waybar" / "colors.css").read_text() == "bg #deadbe\naccent #c0ffee\n"


def test_apply_sets_current_symlink(tmp_path):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    commands.cmd_new(tmp_path, "t", str(wp), do_apply=False)
    commands.cmd_apply(tmp_path, "t")
    assert catalog.current_theme(tmp_path) == "t"


def test_apply_writes_swaylock_block(tmp_path):
    swaycfg = build_catalog(tmp_path)
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    commands.cmd_new(tmp_path, "t", str(wp))
    text = swaycfg.read_text()
    assert "font=Foo" in text                      # structural preserved
    assert "ring=" in text                          # color block injected
    from adorn import render
    assert render.MARKER_BEGIN in text


def test_render_redramatizes_from_palette(tmp_path):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    commands.cmd_new(tmp_path, "t", str(wp), do_apply=False)
    frag = catalog.theme_paths(tmp_path, "t").dir / "apps" / "waybar" / "colors.css"
    frag.write_text("HAND EDIT\n", encoding="utf-8")
    commands.cmd_render(tmp_path, "t")              # regenerate from palette
    assert frag.read_text().startswith("bg #")      # edit overwritten by render
    assert "HAND EDIT" not in frag.read_text()


def test_overrides_flow_to_fragment_on_render(tmp_path):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    commands.cmd_new(tmp_path, "t", str(wp), do_apply=False)
    tp = catalog.theme_paths(tmp_path, "t")
    palette.dump({"bg": "#000000"}, tp.overrides)
    commands.cmd_render(tmp_path, "t")
    assert "bg #000000" in (tp.dir / "apps" / "waybar" / "colors.css").read_text()


def test_cli_render_subcommand(tmp_path):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    cli.main(["--root", str(tmp_path), "new", "t", str(wp), "--no-apply"])
    assert cli.main(["--root", str(tmp_path), "render", "t"]) == 0


def test_effective_palette_merges(tmp_path):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    commands.cmd_new(tmp_path, "t", str(wp), do_apply=False)
    tp = catalog.theme_paths(tmp_path, "t")
    palette.dump({"bg": "#000000"}, tp.overrides)
    eff = commands.effective_palette(tmp_path, "t")
    assert eff["bg"] == "#000000"
    assert "accent" in eff


def test_cli_list_and_current(tmp_path, capsys):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    cli.main(["--root", str(tmp_path), "new", "t", str(wp), "--no-apply"])
    cli.main(["--root", str(tmp_path), "apply", "t"])
    capsys.readouterr()
    cli.main(["--root", str(tmp_path), "list"])
    assert "* t" in capsys.readouterr().out
    cli.main(["--root", str(tmp_path), "current"])
    assert "t" in capsys.readouterr().out


def test_new_with_saturation_floor_and_stats(tmp_path, capsys):
    from adorn import color
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    commands.cmd_new(tmp_path, "pop", str(wp), do_apply=False, saturation_floor=0.5)
    out = capsys.readouterr().out
    assert "compiled 'pop'" in out
    assert "sat floor   0.50" in out
    pal = palette.load(catalog.theme_paths(tmp_path, "pop").palette)
    assert color.hsl(pal["red"])[1] >= 0.45


def test_cli_new_saturation_flag(tmp_path):
    from adorn import color
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    cli.main(["--root", str(tmp_path), "new", "v", str(wp), "--no-apply", "--saturation", "0.4"])
    pal = palette.load(catalog.theme_paths(tmp_path, "v").palette)
    assert color.hsl(pal["red"])[1] >= 0.35


def test_apply_bootstraps_apps_if_missing(tmp_path):
    import shutil
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    commands.cmd_new(tmp_path, "t", str(wp), do_apply=False)
    apps = catalog.theme_paths(tmp_path, "t").dir / "apps"
    shutil.rmtree(apps)                 # simulate a theme with no apps/ yet
    commands.cmd_apply(tmp_path, "t")
    assert (apps / "waybar" / "colors.css").exists()  # apply re-materialized


def test_preview_renders_ansi_swatches(tmp_path, capsys):
    build_catalog(tmp_path)
    wp = tmp_path / "src.png"; make_wallpaper(wp)
    commands.cmd_new(tmp_path, "t", str(wp), do_apply=False)
    capsys.readouterr()
    commands.cmd_preview(tmp_path, "t")
    out = capsys.readouterr().out
    assert "\x1b[48;2;" in out      # ANSI truecolor background = a real swatch
    assert "bg" in out               # role label present
    assert "#" in out                # hex shown
    assert "grad0" in out            # ramp expanded with indices
