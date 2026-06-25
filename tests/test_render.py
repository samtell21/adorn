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


def test_write_block_appends_when_absent(tmp_path):
    cfg = tmp_path / "swaylock.conf"
    cfg.write_text("font=Foo\nindicator-radius=110\n", encoding="utf-8")
    render.write_block(cfg, "ring-color=aabbcc")
    text = cfg.read_text()
    assert "font=Foo" in text                      # structural config preserved
    assert render.MARKER_BEGIN in text and render.MARKER_END in text
    assert "ring-color=aabbcc" in text


def test_write_block_replaces_existing(tmp_path):
    cfg = tmp_path / "swaylock.conf"
    render.write_block(cfg, "ring-color=oldold")    # creates file + block
    render.write_block(cfg, "ring-color=newnew")    # replaces block
    text = cfg.read_text()
    assert "ring-color=newnew" in text
    assert "ring-color=oldold" not in text
    assert text.count(render.MARKER_BEGIN) == 1     # exactly one block


def test_write_block_preserves_surrounding(tmp_path):
    cfg = tmp_path / "c"
    cfg.write_text(f"A=1\n{render.MARKER_BEGIN}\nold\n{render.MARKER_END}\nB=2\n", encoding="utf-8")
    render.write_block(cfg, "new=val")
    text = cfg.read_text()
    assert "A=1" in text and "B=2" in text and "new=val" in text and "old" not in text


def test_write_block_keeps_blank_separator_on_reapply(tmp_path):
    cfg = tmp_path / "c"
    cfg.write_text(f"A=1\n{render.MARKER_BEGIN}\nold\n{render.MARKER_END}\n\n[next]\nB=2\n", encoding="utf-8")
    render.write_block(cfg, "x=1")
    render.write_block(cfg, "x=2")  # re-apply
    text = cfg.read_text()
    assert "\n\n[next]" in text   # blank line before [next] preserved
    assert "B=2" in text and "x=2" in text and "old" not in text
