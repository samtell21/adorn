import subprocess
import pytest
from adorn import catalog, cli, commands, palette


def setup_theme(tmp_path):
    (tmp_path / "schemes" / "default").mkdir(parents=True)
    (tmp_path / "schemes" / "default" / "w.tmpl").write_text("bg {{ bg }}\n")
    (tmp_path / "adorn.toml").write_text(
        '[mood]\nbg_lightness=0.07\n[ramp]\nname="grad"\nlength=7\nhues=[300,215,175,120,40]\n'
        '[[target]]\nname="waybar"\ntemplate="w.tmpl"\nfragment="colors.css"\n'
    )
    wp = tmp_path / "src.png"
    subprocess.run(["magick", "-size", "16x16", "xc:#9b9e61", str(wp)], check=True)
    commands.cmd_new(tmp_path, "t", str(wp), do_apply=False)
    return tmp_path


def test_alter_saturate_single_prints_mapping(tmp_path, capsys):
    setup_theme(tmp_path)
    commands.cmd_alter(tmp_path, "t", ["red"], False, ["saturate", "0.5"])
    out = capsys.readouterr().out
    assert "red" in out and "->" in out
    # not written
    assert "red" not in palette.load(catalog.theme_paths(tmp_path, "t").overrides)


def test_alter_write_scalar_to_overrides(tmp_path):
    setup_theme(tmp_path)
    commands.cmd_alter(tmp_path, "t", ["accent"], True, ["lighten", "0.1"])
    over = palette.load(catalog.theme_paths(tmp_path, "t").overrides)
    assert "accent" in over and over["accent"].startswith("#")


def test_alter_plus_sigil_references_role(tmp_path, capsys):
    setup_theme(tmp_path)
    commands.cmd_alter(tmp_path, "t", ["accent"], False, ["mix", "+magenta"])
    assert "accent" in capsys.readouterr().out


def test_alter_all_colors_saturate(tmp_path, capsys):
    setup_theme(tmp_path)
    commands.cmd_alter(tmp_path, "t", None, False, ["saturate", "0.1"])
    assert capsys.readouterr().out.count("->") >= 10   # one per palette color incl grad0..6


def test_alter_mismatch_is_error(tmp_path):
    setup_theme(tmp_path)
    with pytest.raises(ValueError, match="produced"):
        commands.cmd_alter(tmp_path, "t", None, False, ["color", "#111111"])  # 1 out for N>1


def test_alter_unknown_role_errors(tmp_path):
    setup_theme(tmp_path)
    with pytest.raises(ValueError, match="unknown"):
        commands.cmd_alter(tmp_path, "t", ["nope"], False, ["saturate", "0.1"])


def test_alter_write_ramp_entry_rebuilds_list(tmp_path):
    setup_theme(tmp_path)
    commands.cmd_alter(tmp_path, "t", ["grad0"], True, ["saturate", "0.2"])
    over = palette.load(catalog.theme_paths(tmp_path, "t").overrides)
    assert isinstance(over["grad"], list) and len(over["grad"]) == 7


def test_cli_alter(tmp_path):
    setup_theme(tmp_path)
    assert cli.main(["--root", str(tmp_path), "alter", "t", "-c", "red", "saturate", "0.3"]) == 0


def test_alter_bad_pastel_command_is_clean_error(tmp_path):
    setup_theme(tmp_path)
    with pytest.raises(ValueError, match="pastel failed"):
        commands.cmd_alter(tmp_path, "t", ["red"], False, ["definitelynotapastelcommand"])


def test_cli_rejects_unknown_flag_on_nonalter_subcommand(tmp_path):
    setup_theme(tmp_path)
    with pytest.raises(SystemExit):
        cli.main(["--root", str(tmp_path), "list", "--bogus"])


def test_cli_alter_still_passes_through_command(tmp_path):
    setup_theme(tmp_path)
    assert cli.main(["--root", str(tmp_path), "alter", "t", "-c", "red", "saturate", "0.3"]) == 0
