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


def test_new_theme_dir_creates_then_conflicts(tmp_path):
    d = catalog.new_theme_dir(tmp_path, "fresh")
    assert d.is_dir()
    with pytest.raises(FileExistsError):
        catalog.new_theme_dir(tmp_path, "fresh")


def test_current_theme_ignores_broken_symlink(tmp_path):
    _mk(tmp_path, "a")
    catalog.set_current(tmp_path, "a")
    assert catalog.current_theme(tmp_path) == "a"
    # delete the theme dir out from under the symlink -> dangling link
    import shutil
    shutil.rmtree(tmp_path / "themes" / "a")
    assert catalog.current_theme(tmp_path) is None


def test_set_current_creates_real_symlink(tmp_path):
    _mk(tmp_path, "a")
    catalog.set_current(tmp_path, "a")
    assert (tmp_path / "current").is_symlink()


def test_theme_paths_wallpaper_edge_cases(tmp_path):
    d = _mk(tmp_path, "zero")
    tp = catalog.theme_paths(tmp_path, "zero")
    assert tp.wallpaper == d / "wallpaper"      # sentinel
    assert not tp.wallpaper.exists()            # callers can detect "no wallpaper"

    d2 = _mk(tmp_path, "multi")
    (d2 / "wallpaper.jpg").write_bytes(b"")
    (d2 / "wallpaper.png").write_bytes(b"")
    tp2 = catalog.theme_paths(tmp_path, "multi")
    assert tp2.wallpaper == d2 / "wallpaper.jpg"  # lexicographically first


def test_theme_overrides_absent_is_empty(tmp_path):
    d = _mk(tmp_path, "nometa")
    tp = catalog.theme_paths(tmp_path, "nometa")
    assert catalog.theme_overrides(tp) == {}


def test_theme_overrides_only_scheme_is_empty(tmp_path):
    d = _mk(tmp_path, "bare")
    (d / "theme.toml").write_text('scheme = "default"\n', encoding="utf-8")
    tp = catalog.theme_paths(tmp_path, "bare")
    assert catalog.theme_overrides(tp) == {}


def test_theme_overrides_returns_sections_without_scheme(tmp_path):
    d = _mk(tmp_path, "over")
    (d / "theme.toml").write_text(
        'scheme = "default"\n[mood]\nbg_lightness = 0.03\n[fixed]\naccent = "#abcdef"\n',
        encoding="utf-8",
    )
    tp = catalog.theme_paths(tmp_path, "over")
    ov = catalog.theme_overrides(tp)
    assert "scheme" not in ov
    assert ov == {"mood": {"bg_lightness": 0.03}, "fixed": {"accent": "#abcdef"}}
