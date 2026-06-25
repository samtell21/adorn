"""Render target templates into a theme's apps/ fragments, and manage the
swaylock-style delimited color block for apps that cannot include a file."""
import os
from pathlib import Path

import jinja2

MARKER_BEGIN = "# >>> adorn (managed) >>>"
MARKER_END = "# <<< adorn (managed) <<<"


def make_env(templates_dir) -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(templates_dir)),
        undefined=jinja2.StrictUndefined,
        keep_trailing_newline=True,
    )


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".adorn-tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def materialize(manifest, palette: dict, apps_dir) -> dict:
    """Render each target with a template into apps_dir/<target>/<fragment>.

    Returns {target_name: written_path}. Raises (before writing anything more)
    on a missing role, so a bad template can't leave a half-materialized set.
    """
    env = make_env(manifest.templates_dir)
    rendered = {}
    for target in manifest.targets:
        if not target.template:
            continue
        content = env.get_template(target.template).render(**palette)
        dest = Path(apps_dir) / target.name / target.fragment
        rendered[target.name] = (dest, content)
    written = {}
    for name, (dest, content) in rendered.items():
        _atomic_write(dest, content)
        written[name] = dest
    return written


def write_block(config_path, fragment_text: str) -> None:
    """Replace the adorn-managed block in config_path with fragment_text.

    Appends a fresh block if the markers are absent; creates the file if missing.
    The user's surrounding (structural) config is preserved untouched.
    """
    path = Path(config_path)
    block = f"{MARKER_BEGIN}\n{fragment_text.rstrip(chr(10))}\n{MARKER_END}\n"
    if path.exists():
        text = path.read_text(encoding="utf-8")
        if MARKER_BEGIN in text and MARKER_END in text:
            pre = text[: text.index(MARKER_BEGIN)]
            post = text[text.index(MARKER_END) + len(MARKER_END):].removeprefix("\n")
            new = pre + block + post
        else:
            new = text.rstrip("\n") + "\n\n" + block
    else:
        new = block
    _atomic_write(path, new)
