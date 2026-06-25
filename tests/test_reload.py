import shlex
import types

from adorn import reload as reload_mod
from adorn.manifest import Target


def test_run_reload_executes_command(tmp_path):
    marker = tmp_path / "reloaded"
    t = Target("x", reload=f"touch {marker}")
    reload_mod.run_reload(t)
    assert marker.exists()


def test_run_reload_none_is_noop(tmp_path):
    reload_mod.run_reload(Target("x"))  # no error


def test_run_reloads_all(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    m = types.SimpleNamespace(
        targets=(
            Target("a", reload=f"touch {a}"),
            Target("b", reload=f"touch {b}"),
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


def test_set_wallpaper_quotes_path_with_metachars(tmp_path):
    # a wallpaper path containing a shell metacharacter must not inject a command
    sentinel = tmp_path / "PWNED"
    evil = tmp_path / f"a; touch {sentinel} #.jpg"
    rec = tmp_path / "rec"
    # the wallpaper command writes the (quoted) path to rec; injection would create sentinel
    m = types.SimpleNamespace(wallpaper_command=f"echo {{path}} > {rec}")
    reload_mod.set_wallpaper(m, evil)
    assert not sentinel.exists()            # injection did NOT execute
    # the path appears in output, but as a quoted string (not executed)
    assert str(evil) in rec.read_text()
