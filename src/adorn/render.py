"""Render targets to outputs (Jinja2 or verbatim files/), then write atomically."""
import os
from pathlib import Path

import jinja2


def make_env(templates_dir) -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )


def render_all(manifest, palette: dict, files_dir) -> dict:
    """Return {output_path: content} for every target. Raises before any write."""
    env = make_env(manifest.templates_dir)
    outputs: dict = {}
    for target in manifest.targets:
        override = Path(files_dir) / target.name
        if override.is_dir():
            inner = next((p for p in sorted(override.iterdir()) if p.is_file()), None)
            if inner is None:
                raise ValueError(f"files/{target.name}/ exists but is empty")
            outputs[target.output] = inner.read_text()
        elif target.template:
            outputs[target.output] = env.get_template(target.template).render(**palette)
        else:
            raise ValueError(
                f"target {target.name!r} has no template and no files/ override"
            )
    return outputs


def write_all(outputs: dict) -> None:
    """Write each output atomically (temp file + os.replace)."""
    for path, content in outputs.items():
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".adorn-tmp")
        tmp.write_text(content)
        os.replace(tmp, path)
