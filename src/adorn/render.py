"""Render target templates into a theme's apps/ fragments."""
import os
from pathlib import Path

import jinja2

from . import color


def make_env(templates_dir) -> jinja2.Environment:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )
    env.filters["mix"] = color.mix
    env.filters["lighten"] = color.lighten
    env.filters["darken"] = color.darken
    return env


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".adorn-tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def materialize(manifest, context: dict, apps_dir, templates_dir) -> dict:
    """Render each target with a template into apps_dir/<target>/<fragment>.

    Returns {target_name: written_path}. Raises (before writing anything more)
    on a missing role, so a bad template can't leave a half-materialized set.
    """
    env = make_env(templates_dir)
    rendered = {}
    for target in manifest.targets:
        if not target.template:
            continue
        content = env.get_template(target.template).render(**context)
        dest = Path(apps_dir) / target.name / target.fragment
        rendered[target.name] = (dest, content)
    written = {}
    for name, (dest, content) in rendered.items():
        _atomic_write(dest, content)
        written[name] = dest
    return written
