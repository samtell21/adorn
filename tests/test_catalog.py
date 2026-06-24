import pytest

from adorn import catalog


def _mk(root, name):
    d = root / "themes" / name
    d.mkdir(parents=True)
    return d


def test_list_empty(tmp_path):
    assert catalog.list_themes(tmp_path) == []


def test_list_sorted(tmp_path):
    _mk(tmp_path, "oceanic")
    _mk(tmp_path, "succulents")
    assert catalog.list_themes(tmp_path) == ["oceanic", "succulents"]


def test_current_none_then_set_and_switch(tmp_path):
    _mk(tmp_path, "a")
    _mk(tmp_path, "b")
    assert catalog.current_theme(tmp_path) is None
    catalog.set_current(tmp_path, "a")
    assert catalog.current_theme(tmp_path) == "a"
    catalog.set_current(tmp_path, "b")
    assert catalog.current_theme(tmp_path) == "b"


def test_theme_paths(tmp_path):
    d = _mk(tmp_path, "x")
    (d / "wallpaper.jpg").write_bytes(b"")
    tp = catalog.theme_paths(tmp_path, "x")
    assert tp.dir == d
    assert tp.wallpaper == d / "wallpaper.jpg"
    assert tp.palette == d / "palette.toml"
    assert tp.overrides == d / "overrides.toml"
    assert tp.files == d / "files"


def test_new_theme_dir_creates_then_conflicts(tmp_path):
    d = catalog.new_theme_dir(tmp_path, "fresh")
    assert d.is_dir()
    with pytest.raises(FileExistsError):
        catalog.new_theme_dir(tmp_path, "fresh")
