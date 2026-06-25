import types
from pathlib import Path

from adorn import render
from adorn.manifest import Target


def manifest_with(tmp_path, targets):
    (tmp_path / "templates").mkdir(exist_ok=True)
    return types.SimpleNamespace(templates_dir=tmp_path / "templates", targets=tuple(targets))


def test_materialize_renders_into_apps_dir(tmp_path):
    (tmp_path / "templates" / "waybar.tmpl").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "templates" / "waybar.tmpl").write_text("bg {{ bg }}\n")
    m = manifest_with(tmp_path, [Target("waybar", template="waybar.tmpl", fragment="colors.css")])
    apps = tmp_path / "apps"
    written = render.materialize(m, {"bg": "#111111"}, apps)
    dest = apps / "waybar" / "colors.css"
    assert dest.read_text() == "bg #111111\n"
    assert written["waybar"] == dest


def test_materialize_ramp_indexing(tmp_path):
    (tmp_path / "templates").mkdir(exist_ok=True)
    (tmp_path / "templates" / "g.tmpl").write_text("{{ grad[0] }}|{{ grad[1] }}")
    m = manifest_with(tmp_path, [Target("g", template="g.tmpl", fragment="c")])
    render.materialize(m, {"grad": ["#aaaaaa", "#bbbbbb"]}, tmp_path / "apps")
    assert (tmp_path / "apps" / "g" / "c").read_text() == "#aaaaaa|#bbbbbb"


def test_materialize_missing_role_raises(tmp_path):
    import jinja2
    (tmp_path / "templates").mkdir(exist_ok=True)
    (tmp_path / "templates" / "x.tmpl").write_text("{{ missing }}")
    m = manifest_with(tmp_path, [Target("x", template="x.tmpl", fragment="c")])
    import pytest
    with pytest.raises(jinja2.UndefinedError):
        render.materialize(m, {"bg": "#111111"}, tmp_path / "apps")


def test_materialize_passes_nonpalette_context(tmp_path):
    (tmp_path / "templates").mkdir(exist_ok=True)
    (tmp_path / "templates" / "w.tmpl").write_text("wp {{ wallpaper }}")
    m = manifest_with(tmp_path, [Target("sway", template="w.tmpl", fragment="colors")])
    render.materialize(m, {"wallpaper": "/x/wall.jpg"}, tmp_path / "apps")
    assert (tmp_path / "apps" / "sway" / "colors").read_text() == "wp /x/wall.jpg"
