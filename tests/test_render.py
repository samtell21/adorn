import types
from pathlib import Path

import jinja2
import pytest

from adorn import render
from adorn.manifest import Target


def manifest_with(tmp_path, targets):
    (tmp_path / "templates").mkdir(exist_ok=True)
    return types.SimpleNamespace(
        templates_dir=tmp_path / "templates", targets=tuple(targets)
    )


def test_renders_template_with_palette(tmp_path):
    (tmp_path / "templates" / "kitty.conf.tmpl").parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "templates" / "kitty.conf.tmpl").write_text("background {{ bg }}\n")
    out = tmp_path / "out" / "colors.conf"
    m = manifest_with(tmp_path, [Target("kitty", out, "kitty.conf.tmpl", None)])
    outputs = render.render_all(m, {"bg": "#111111"}, tmp_path / "files")
    assert outputs[out] == "background #111111\n"


def test_ramp_list_indexing(tmp_path):
    (tmp_path / "templates").mkdir(exist_ok=True)
    (tmp_path / "templates" / "g.tmpl").write_text("{{ grad[0] }}|{{ grad[1] }}")
    out = tmp_path / "g.out"
    m = manifest_with(tmp_path, [Target("g", out, "g.tmpl", None)])
    outputs = render.render_all(m, {"grad": ["#aaaaaa", "#bbbbbb"]}, tmp_path / "files")
    assert outputs[out] == "#aaaaaa|#bbbbbb"


def test_missing_role_raises(tmp_path):
    (tmp_path / "templates").mkdir(exist_ok=True)
    (tmp_path / "templates" / "x.tmpl").write_text("{{ missing }}")
    m = manifest_with(tmp_path, [Target("x", tmp_path / "x.out", "x.tmpl", None)])
    with pytest.raises(jinja2.UndefinedError):
        render.render_all(m, {"bg": "#111111"}, tmp_path / "files")


def test_files_override_used_verbatim(tmp_path):
    (tmp_path / "templates").mkdir(exist_ok=True)
    (tmp_path / "templates" / "wofi.tmpl").write_text("TEMPLATED {{ bg }}")
    override_dir = tmp_path / "files" / "wofi"
    override_dir.mkdir(parents=True)
    (override_dir / "style.css").write_text("VERBATIM CONTENT")
    out = tmp_path / "wofi.out"
    m = manifest_with(tmp_path, [Target("wofi", out, "wofi.tmpl", None)])
    outputs = render.render_all(m, {"bg": "#111111"}, tmp_path / "files")
    assert outputs[out] == "VERBATIM CONTENT"


def test_write_all_creates_dirs_and_files(tmp_path):
    out = tmp_path / "deep" / "nested" / "colors.conf"
    render.write_all({out: "hello\n"})
    assert out.read_text() == "hello\n"


def test_no_template_no_override_raises(tmp_path):
    m = manifest_with(tmp_path, [Target("bad", tmp_path / "b.out", None, None)])
    with pytest.raises(ValueError, match="no template"):
        render.render_all(m, {}, tmp_path / "files")
