import pytest

from adorn import cli, commands, manifest


def test_load_missing_manifest_raises_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="adorn init"):
        manifest.load(tmp_path / "adorn.toml")


def test_cmd_init_scaffolds_config(tmp_path, capsys):
    commands.cmd_init(tmp_path)
    assert (tmp_path / "adorn.toml").exists()
    assert (tmp_path / "templates").is_dir()
    assert (tmp_path / "themes").is_dir()
    out = capsys.readouterr().out
    assert "created" in out.lower()


def test_cmd_init_refuses_to_clobber(tmp_path):
    commands.cmd_init(tmp_path)
    with pytest.raises(FileExistsError, match="already exists"):
        commands.cmd_init(tmp_path)


def test_cli_init_then_manifest_loads(tmp_path):
    rc = cli.main(["--root", str(tmp_path), "init"])
    assert rc == 0
    # starter manifest parses (has [mood]/[ramp]/[extract]); no targets yet is fine for load?
    # load() raises on zero targets, so just assert the file exists and is valid TOML.
    import tomllib
    data = tomllib.loads((tmp_path / "adorn.toml").read_text(encoding="utf-8"))
    assert "extract" in data and "mood" in data


def test_cli_missing_manifest_is_clean_error(tmp_path, capsys):
    # new on a root with no manifest -> exit 1 + friendly stderr, no traceback
    rc = cli.main(["--root", str(tmp_path / "nope"), "new", "x", str(tmp_path / "img.png")])
    assert rc == 1
    err = capsys.readouterr().err
    assert err.startswith("adorn:")
    assert "adorn init" in err
