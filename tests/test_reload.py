import types

from adorn import reload as reload_mod
from adorn.manifest import Target


def test_run_reload_executes_command(tmp_path):
    marker = tmp_path / "reloaded"
    t = Target("x", tmp_path / "out", None, f"touch {marker}")
    reload_mod.run_reload(t)
    assert marker.exists()


def test_run_reload_none_is_noop(tmp_path):
    reload_mod.run_reload(Target("x", tmp_path / "out", None, None))  # no error


def test_run_reloads_all(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    m = types.SimpleNamespace(
        targets=(
            Target("a", tmp_path / "oa", None, f"touch {a}"),
            Target("b", tmp_path / "ob", None, f"touch {b}"),
        )
    )
    reload_mod.run_reloads(m)
    assert a.exists() and b.exists()


def test_set_wallpaper_substitutes_path(tmp_path):
    rec = tmp_path / "rec"
    m = types.SimpleNamespace(wallpaper_command=f"echo {{path}} > {rec}")
    reload_mod.set_wallpaper(m, tmp_path / "wall.jpg")
    assert str(tmp_path / "wall.jpg") in rec.read_text()


def test_set_wallpaper_none_is_noop():
    m = types.SimpleNamespace(wallpaper_command=None)
    reload_mod.set_wallpaper(m, "/whatever.jpg")  # no error
